"""Stage 2b: HDBSCAN clustering of the novel pool.

Replaces the brittle regex normalization in cluster.py. Summaries from the
triage step are re-embedded, then HDBSCAN groups semantically similar
techniques without needing a hand-specified k. An LLM call labels each
surviving cluster with an issue_type slug, applicable AEM flavors, and a
risk tier.

Survival filter: ≥ 4 PRs, ≥ 2 distinct repos, ≥ 70% directional consistency
(same threshold the old statistical pipeline used, so evidence quality doesn't
regress).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.llm.client import LLMError, complete_json
from cwv_playbook_miner.triage.embed import embed_texts
from cwv_playbook_miner.triage.triage import TriageRecord

MIN_CLUSTER_PRS = 4
MIN_CLUSTER_REPOS = 2
MIN_DIRECTIONAL_CONSISTENCY = 0.70

LABEL_SYSTEM_PROMPT = """You are an AEM web-performance architect. For each cluster of related GitHub PRs,
produce a compact issue_type identifier and AEM applicability assessment.

Rules for issue_type:
- kebab-case, 2-4 words, describes the performance problem being fixed (not the fix)
- Examples: "dom-complexity", "render-blocking-resource", "unused-client-code", "image-format"
- Must be distinct from these already-existing types:
  blocking-resource, bundling, compression, font-fallback, font-format, font-preload,
  general, image-sizing, inline-css, interaction, js-execution, layout-shift, lcp-image,
  request-chain, resource-hints, resource-preload, third-party, ttfb, unused-code

Rules for applicable_flavors:
- Subset of: ["eds", "cs", "ams", "headless"]
- eds: excluded when fix requires server-side rendering or arbitrary <head> edits not supported by EDS
- ams: excluded when fix is only relevant to modern JS toolchain (tree-shaking, ESM)
- headless: included only when the technique works in a client-side-only rendering model

Rules for risk_tier:
- low: agent can auto-apply with high confidence (e.g. add width/height attribute)
- medium: needs validation before applying (e.g. split a bundle, change load order)
- high: recommendation-only — too much runtime context needed for safe auto-fix

Return strict JSON:
{"clusters": [{
  "cluster_id": <int>,
  "issue_type": "<kebab-case>",
  "description": "<one sentence: the problem and which CWV metric it affects>",
  "applicable_flavors": ["eds"|"cs"|"ams"|"headless", ...],
  "risk_tier": "low|medium|high",
  "aem_rationale": "<1-2 sentences: why these flavors and this tier>"
}]}"""


@dataclass
class NovelCluster:
    cluster_id: int
    issue_type: str
    description: str
    applicable_flavors: list[str]
    risk_tier: str
    aem_rationale: str
    source_pr_ids: list[str]
    distinct_repo_count: int
    positive_count: int
    negative_count: int
    directional_consistency: float
    representative_summaries: list[str] = field(default_factory=list)


def write_jsonl(clusters: list[NovelCluster], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in clusters:
            f.write(json.dumps(asdict(c)) + "\n")


def read_jsonl(path: Path) -> list[NovelCluster]:
    clusters = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            clusters.append(NovelCluster(**json.loads(line)))
    return clusters


def _hdbscan_labels(embeddings: np.ndarray, min_cluster_size: int = 4) -> np.ndarray:
    """Return cluster labels (-1 = noise). Tries sklearn 1.3+ HDBSCAN first,
    falls back to the standalone hdbscan package."""
    try:
        from sklearn.cluster import HDBSCAN  # type: ignore[import]
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=2,
            metric="cosine",
            cluster_selection_method="eom",
        )
        return clusterer.fit_predict(embeddings.astype(np.float64))
    except ImportError:
        pass

    try:
        import hdbscan as hdbscan_pkg  # type: ignore[import]
        clusterer = hdbscan_pkg.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=2,
            metric="euclidean",  # embeddings are already unit-norm
        )
        return clusterer.fit_predict(embeddings.astype(np.float64))
    except ImportError as exc:
        raise ImportError(
            "scikit-learn >= 1.3 or the hdbscan package is required for semantic "
            "clustering. Install one: pip install 'scikit-learn>=1.3'"
        ) from exc


def _label_clusters(
    cluster_groups: dict[int, list[tuple[TriageRecord, PRRecord]]],
    backend: str,
    model: str | None,
    timeout: int,
) -> dict[int, dict]:
    """Ask the LLM to label all clusters in one batched call."""
    payload = []
    for cid, items in cluster_groups.items():
        summaries = [tr.summary for tr, _ in items[:8]]
        repos = list({pr.repo for _, pr in items})[:5]
        payload.append({
            "cluster_id": cid,
            "technique_summaries": summaries,
            "repos": repos,
            "pr_count": len(items),
        })

    user = json.dumps({"clusters_to_label": payload})
    try:
        result = complete_json(LABEL_SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
        return {c["cluster_id"]: c for c in result.get("clusters", [])}
    except (LLMError, KeyError, TypeError):
        return {}


def cluster_novel_records(
    triage_records: list[TriageRecord],
    pr_records_by_id: dict[str, PRRecord],
    *,
    embed_provider: str = "openai",
    embed_model: str | None = None,
    embed_base_url: str | None = None,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 120,
    min_cluster_size: int = MIN_CLUSTER_PRS,
) -> list[NovelCluster]:
    """Full Stage 2b. Returns clusters that passed the survival filter."""

    novel = [tr for tr in triage_records if tr.route == "novel"]
    print(f"[semantic-cluster] {len(novel)} novel records to cluster")
    if not novel:
        return []

    # Re-embed summaries
    summaries = [tr.summary for tr in novel]
    embed_kwargs = dict(provider=embed_provider, model=embed_model, base_url=embed_base_url)
    print(f"[semantic-cluster] embedding {len(summaries)} summaries...")
    embeddings = embed_texts(summaries, **embed_kwargs)

    # HDBSCAN
    labels = _hdbscan_labels(embeddings, min_cluster_size=min_cluster_size)
    unique_labels = set(labels) - {-1}
    print(f"[semantic-cluster] HDBSCAN: {len(unique_labels)} clusters, "
          f"{(labels == -1).sum()} noise points")

    # Group records by cluster
    groups: dict[int, list[tuple[TriageRecord, PRRecord]]] = defaultdict(list)
    for tr, label in zip(novel, labels):
        if label == -1:
            continue
        pr = pr_records_by_id.get(tr.record_id)
        if pr:
            groups[int(label)].append((tr, pr))

    # Survival filter
    surviving: dict[int, list[tuple[TriageRecord, PRRecord]]] = {}
    for cid, items in groups.items():
        repos = {pr.repo for _, pr in items}
        pos = sum(1 for tr, _ in items if tr.signal_type == "perf_improvement")
        neg = sum(1 for tr, _ in items if tr.signal_type == "perf_decrease")
        total = pos + neg
        consistency = pos / total if total > 0 else 0.0

        if (len(items) >= MIN_CLUSTER_PRS
                and len(repos) >= MIN_CLUSTER_REPOS
                and (total == 0 or consistency >= MIN_DIRECTIONAL_CONSISTENCY
                     or (1 - consistency) >= MIN_DIRECTIONAL_CONSISTENCY)):
            surviving[cid] = items

    print(f"[semantic-cluster] {len(surviving)} clusters survived filter "
          f"(of {len(groups)} total)")

    # LLM labeling in one batch call
    labels_by_id = _label_clusters(surviving, backend, model, timeout)

    # Build NovelCluster objects
    result = []
    for cid, items in surviving.items():
        repos = {pr.repo for _, pr in items}
        pos = sum(1 for tr, _ in items if tr.signal_type == "perf_improvement")
        neg = sum(1 for tr, _ in items if tr.signal_type == "perf_decrease")
        total = pos + neg
        consistency = pos / total if total > 0 else 0.0

        label_info = labels_by_id.get(cid, {})
        result.append(NovelCluster(
            cluster_id=cid,
            issue_type=label_info.get("issue_type", f"novel-type-{cid}"),
            description=label_info.get("description", ""),
            applicable_flavors=label_info.get("applicable_flavors", ["eds", "cs", "ams"]),
            risk_tier=label_info.get("risk_tier", "medium"),
            aem_rationale=label_info.get("aem_rationale", ""),
            source_pr_ids=[pr.id for _, pr in items],
            distinct_repo_count=len(repos),
            positive_count=pos,
            negative_count=neg,
            directional_consistency=round(consistency, 4),
            representative_summaries=[tr.summary for tr, _ in items[:6]],
        ))

    return sorted(result, key=lambda c: len(c.source_pr_ids), reverse=True)
