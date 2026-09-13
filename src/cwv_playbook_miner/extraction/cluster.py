"""Stage 3+4: bottom-up clustering, coherence verification, then relevance +
category labeling -- all on real evidence, never short phrases.

HDBSCAN can density-chain a "path" of loosely-related items (A similar to
B similar to C, but A and C not actually similar) into one cluster, so
nothing downstream of raw clustering can be trusted without checking. Every
candidate cluster gets read in full (several complete PR evidence excerpts,
not phrases) by a dedicated coherence-verification call before anything
gets labeled or generated from it. A cluster that fails coherence is
rejected outright (its PRs return to the unclustered pool) rather than
auto-split -- splitting on partial evidence risks inventing a new error to
replace the one being fixed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.extraction.technique_extract import TechniqueExtraction, build_embedding_text
from cwv_playbook_miner.llm.client import LLMError, complete_json
from cwv_playbook_miner.routing.route import RoutingRecord
from cwv_playbook_miner.embedding import embed_texts

MIN_CLUSTER_PRS = 4
MIN_CLUSTER_REPOS = 2
MIN_DIRECTIONAL_CONSISTENCY = 0.70
COHERENCE_SAMPLE_SIZE = 8
LABEL_EVIDENCE_SIZE = 8
EVIDENCE_PATCH_CHARS = 1200
EVIDENCE_COMMENT_CHARS = 800

COHERENCE_SYSTEM_PROMPT = """You are checking whether a group of PRs, grouped by embedding similarity,
actually implement the SAME concrete technique -- same mechanism, same affected resource. Embedding
similarity can density-chain loosely-related items together (A similar to B similar to C, but A and C
not actually alike) -- your job is to catch that.

For each cluster, read the full evidence for several of its member PRs and decide:
- "coherent": yes, these PRs genuinely implement the same technique
- "incoherent": no -- either it's noise, or it's a mix of genuinely different techniques

Be strict: superficial similarity (both touch images, both mention "reduce size") is not enough --
the concrete mechanism must actually match.

Return strict JSON, one entry per input cluster, same order:
{"verdicts": [{"cluster_id": <int>, "coherent": true|false, "reasoning": "<one sentence>"}]}"""

LABEL_SYSTEM_PROMPT = """You are an AEM web-performance architect. For each cluster of PRs (already
verified to be one coherent technique), read the real evidence and produce:

- cwv_relevant: false if these PRs are CI/test/build-tooling, docs, observability/telemetry,
  linting, or dependency/tooling upgrades with no runtime behavior change for an end user -- true
  only when the technique demonstrably changes browser-side load/render/execution behavior
- issue_type: kebab-case, 2-4 words, describes the performance problem being fixed (not the fix).
  Must be distinct from these already-existing types: blocking-resource, bundling, compression,
  font-fallback, font-format, font-preload, general, image-sizing, inline-css, interaction,
  js-execution, layout-shift, lcp-image, request-chain, resource-hints, resource-preload,
  third-party, ttfb, unused-code
- description: one sentence -- the problem and which CWV metric it affects
- applicable_flavors: subset of ["eds", "cs", "ams", "headless"] -- eds excluded when the fix
  requires server-side rendering or arbitrary <head> edits; ams excluded when only relevant to a
  modern JS toolchain; headless included only for client-side-only rendering
- risk_tier: low (auto-apply with high confidence) | medium (needs validation) | high
  (recommendation-only)
- aem_rationale: 1-2 sentences -- why these flavors and this tier

Return strict JSON, one entry per input cluster, same order:
{"clusters": [{"cluster_id": <int>, "cwv_relevant": true|false, "issue_type": "...",
  "description": "...", "applicable_flavors": [...], "risk_tier": "...", "aem_rationale": "..."}]}"""

# Labeling above only checks issue_type against the curated set (a fixed
# list in the prompt) -- it has zero visibility into sibling novel clusters
# being labeled in this same run, since each cluster is labeled in its own
# independent call. Confirmed live: this let 11 separately-formed clusters
# all independently describe "convert CommonJS/barrel imports to ESM so
# bundlers can tree-shake" (different clusters because their embedding text
# named different libraries -- Lodash, an SDK, an icon package -- so
# HDBSCAN correctly saw them as embedding-distant even though a person
# reads them as the same fix), and 2 clusters both landed on the literal
# name "excess-javascript-payload" with zero source-PR overlap. This is a
# dedicated pass over every surviving cluster's label together (cheap --
# short issue_type/description/aem_rationale strings, not full PR evidence)
# specifically to catch that; nothing upstream of it ever compares one
# cluster to another.
DEDUP_SYSTEM_PROMPT = """You are deduplicating a set of already-labeled novel CWV playbook
candidates. Each was clustered and labeled independently (by embedding similarity of its own PRs),
so two candidates can describe the SAME underlying technique even when their issue_type names and
example libraries differ -- e.g. one cluster keyed off a Lodash import and another off an unrelated
SDK's barrel import can both really mean "replace barrel/CommonJS imports with subpath ESM imports
so bundlers can tree-shake".

For each cluster below (issue_type, description, aem_rationale, member_count), find GROUPS of
cluster_ids that describe the same underlying technique -- same root mechanism and fix, not just the
same broad category. "Reduce JS payload" is too broad a category to group on; "convert CommonJS/
barrel imports to ESM for tree-shaking" is a specific-enough mechanism that two clusters CAN share.
Only group clusters a developer would call duplicates if shown both playbooks side by side.

Return strict JSON:
{"groups": [{"cluster_ids": [<int>, <int>, ...], "reasoning": "<one sentence: the shared mechanism>"}]}
Only include groups of 2 or more -- omit every cluster that is genuinely distinct from all others."""


@dataclass
class NovelCluster:
    cluster_id: int
    issue_type: str = ""
    description: str = ""
    applicable_flavors: list[str] = field(default_factory=list)
    risk_tier: str = "medium"
    aem_rationale: str = ""
    source_pr_ids: list[str] = field(default_factory=list)
    distinct_repo_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    directional_consistency: float = 0.0
    pr_directions: dict[str, str] = field(default_factory=dict)


def _slugify(text: str) -> str:
    """Guarantees kebab-case regardless of what the labeling LLM returns --
    the prompt asks for it, but has been observed to occasionally return
    space-separated words instead (e.g. "service-worker caching"), which
    would otherwise land directly in a filename."""
    import re as _re
    s = _re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return s.strip("-") or "unnamed-technique"


def _hdbscan_labels(embeddings: np.ndarray, min_cluster_size: int) -> np.ndarray:
    from sklearn.cluster import HDBSCAN
    clusterer = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=2,
                         metric="cosine", cluster_selection_method="eom")
    return clusterer.fit_predict(embeddings.astype(np.float64))


def _resolve_direction(record: PRRecord, extraction: TechniqueExtraction) -> str | None:
    if record.signal_type == "perf_improvement":
        return "positive"
    if record.signal_type == "perf_decrease":
        return "negative"
    if record.signal_type == "perf_flagged" and extraction.direction in ("positive", "negative"):
        return extraction.direction
    return None


def _evidence_block(record: PRRecord, extraction: TechniqueExtraction) -> str:
    files = sorted(record.changed_files, key=lambda f: len(f.get("patch") or ""), reverse=True)[:3]
    file_text = "\n---\n".join(
        f"File: {f.get('filename','')}\n{(f.get('patch') or '')[:EVIDENCE_PATCH_CHARS]}"
        for f in files if f.get("patch")
    )
    comments = sorted(record.pr_comments or [], key=lambda c: c.get("created_at") or "")[:5]
    comment_text = "\n".join(
        f"  [{c.get('kind')}/{c.get('author')}] {(c.get('body') or '')[:200]}" for c in comments
    )[:EVIDENCE_COMMENT_CHARS]
    return (
        f"PR: {record.id}\n"
        f"Title: {record.title or '(none)'}\n"
        f"Technique: {extraction.technique} | Mechanism: {extraction.mechanism}\n"
        f"Resource: {extraction.affected_resource} | Phase: {extraction.render_phase}\n"
        + (f"Human signal: {(record.human_signal_text or '')[:300]}\n" if record.human_signal_text else "")
        + (f"Discussion:\n{comment_text}\n" if comment_text else "")
        + (f"Diff:\n{file_text}" if file_text else "")
    )


CLUSTER_CALL_BATCH_SIZE = 4  # clusters per LLM call -- a single call with all
# clusters' full evidence at once measured ~2M chars (~508K tokens) on a real
# 72-cluster run and blew the context window (HTTP 400). Each cluster brings
# up to 8 full PR evidence excerpts, so this has to be batched same as every
# other per-record call in this pipeline.


def _chunk(groups: dict[int, list], size: int) -> list[dict[int, list]]:
    items = list(groups.items())
    return [dict(items[s:s + size]) for s in range(0, len(items), size)]


def _run_cluster_batches(batches: list[dict], call_fn, label: str, workers: int) -> list:
    """Runs call_fn(batch, bi) -> result over batches, optionally in
    parallel (ThreadPoolExecutor) -- shared by coherence-check and
    labeling, whose only difference is call_fn and how the result gets
    merged into the caller's `out` dict. Only the main thread ever touches
    a shared dict; workers just return their batch's result."""
    if workers <= 1:
        return [call_fn(batch, bi) for bi, batch in enumerate(batches, 1)]
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = [None] * len(batches)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(call_fn, batch, bi): bi - 1 for bi, batch in enumerate(batches, 1)}
        completed = 0
        for future in as_completed(futures):
            results[futures[future]] = future.result()
            completed += 1
            print(f"    {label} {completed}/{len(batches)} batches")
    return results


def _verify_coherence(
    groups: dict[int, list[tuple[PRRecord, TechniqueExtraction]]],
    backend: str, model: str | None, timeout: int, workers: int = 1,
) -> dict[int, bool]:
    import random
    batches = _chunk(groups, CLUSTER_CALL_BATCH_SIZE)

    def _run(batch, bi):
        payload = []
        for cid, items in batch.items():
            sample = random.sample(items, min(COHERENCE_SAMPLE_SIZE, len(items)))
            evidence = "\n\n====\n\n".join(_evidence_block(pr, ext) for pr, ext in sample)
            payload.append({"cluster_id": cid, "member_count": len(items), "evidence": evidence})
        user = json.dumps({"clusters": payload}, ensure_ascii=False)
        verdicts: dict[int, bool] = {}
        try:
            result = complete_json(COHERENCE_SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
            for v in result.get("verdicts", []):
                verdicts[v["cluster_id"]] = bool(v.get("coherent"))
        except LLMError as exc:
            print(f"    coherence check batch {bi}/{len(batches)} LLM error: {exc} -- rejecting this batch")
        for cid in batch:
            verdicts.setdefault(cid, False)  # missing verdict -> not confirmed, don't guess
        return verdicts

    out: dict[int, bool] = {}
    for verdicts in _run_cluster_batches(batches, _run, "coherence-checked", workers):
        out.update(verdicts)
    return out


def _label_clusters(
    groups: dict[int, list[tuple[PRRecord, TechniqueExtraction]]],
    backend: str, model: str | None, timeout: int, workers: int = 1,
) -> dict[int, dict]:
    import random
    batches = _chunk(groups, CLUSTER_CALL_BATCH_SIZE)

    def _run(batch, bi):
        payload = []
        for cid, items in batch.items():
            sample = random.sample(items, min(LABEL_EVIDENCE_SIZE, len(items)))
            evidence = "\n\n====\n\n".join(_evidence_block(pr, ext) for pr, ext in sample)
            payload.append({"cluster_id": cid, "member_count": len(items), "evidence": evidence})
        user = json.dumps({"clusters": payload}, ensure_ascii=False)
        labels: dict[int, dict] = {}
        try:
            result = complete_json(LABEL_SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
            for c in result.get("clusters", []):
                labels[c["cluster_id"]] = c
        except (LLMError, KeyError, TypeError) as exc:
            print(f"    labeling batch {bi}/{len(batches)} LLM error: {exc} -- skipping this batch")
        return labels

    out: dict[int, dict] = {}
    for labels in _run_cluster_batches(batches, _run, "labeled", workers):
        out.update(labels)
    return out


def _deduplicate_clusters(
    surviving: dict[int, list[tuple[PRRecord, TechniqueExtraction]]],
    labels_by_id: dict[int, dict],
    backend: str, model: str | None, timeout: int,
) -> dict[int, int]:
    """Returns {duplicate_cluster_id: primary_cluster_id} -- the duplicate
    should be dropped, not merged into the primary. Merging two clusters
    that HDBSCAN formed separately risks combining PRs whose diffs differ
    in exactly the ways that made them embed apart in the first place;
    dropping the smaller-evidence duplicate in favor of the cluster with
    more source PRs is the same "reject, don't auto-fix" caution the
    coherence check already applies to an incoherent cluster.

    Runs as a single call (not batched): cluster counts seen in practice
    are in the tens, and this payload is short per-cluster labels, not full
    PR evidence, so it stays small even then."""
    payload = [
        {"cluster_id": cid, "issue_type": labels_by_id[cid].get("issue_type", ""),
         "description": labels_by_id[cid].get("description", ""),
         "aem_rationale": labels_by_id[cid].get("aem_rationale", ""),
         "member_count": len(g)}
        for cid, g in surviving.items() if cid in labels_by_id
    ]
    if len(payload) < 2:
        return {}

    user = json.dumps({"clusters": payload}, ensure_ascii=False)
    try:
        result = complete_json(DEDUP_SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
    except LLMError as exc:
        print(f"    dedup check LLM error: {exc} -- skipping dedup, no clusters dropped")
        return {}

    duplicate_of: dict[int, int] = {}
    for group in result.get("groups", []):
        ids = [cid for cid in group.get("cluster_ids", []) if cid in surviving]
        if len(ids) < 2:
            continue
        primary = max(ids, key=lambda cid: len(surviving[cid]))
        for cid in ids:
            if cid != primary:
                duplicate_of[cid] = primary
        print(f"    dedup: {[labels_by_id[c].get('issue_type') for c in ids]} -> keeping "
              f"{labels_by_id[primary].get('issue_type')!r} ({group.get('reasoning', '')})")
    return duplicate_of


def _consistency_stats(items: list[tuple[PRRecord, TechniqueExtraction]]) -> tuple[int, int, bool]:
    pos = sum(1 for pr, ext in items if _resolve_direction(pr, ext) == "positive")
    neg = sum(1 for pr, ext in items if _resolve_direction(pr, ext) == "negative")
    total = pos + neg
    if total == 0:
        return pos, neg, False
    return pos, neg, (max(pos, neg) / total) >= MIN_DIRECTIONAL_CONSISTENCY


def cluster_and_label(
    routing_records: list[RoutingRecord],
    pr_by_id: dict[str, PRRecord],
    extraction_by_id: dict[str, TechniqueExtraction],
    *,
    embed_provider: str = "openai",
    embed_model: str | None = None,
    embed_base_url: str | None = None,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 180,
    min_cluster_size: int = MIN_CLUSTER_PRS,
    workers: int = 1,
) -> list[NovelCluster]:
    novel_ids = [r.record_id for r in routing_records if r.route == "novel"]
    items = [(pr_by_id[rid], extraction_by_id[rid]) for rid in novel_ids
             if rid in pr_by_id and rid in extraction_by_id]
    print(f"[cluster] {len(items)} novel records to cluster")
    if not items:
        return []

    texts = [build_embedding_text(ext) for _, ext in items]
    embeddings = embed_texts(texts, provider=embed_provider, model=embed_model, base_url=embed_base_url)

    labels = _hdbscan_labels(embeddings, min_cluster_size)
    unique = set(labels) - {-1}
    print(f"[cluster] HDBSCAN: {len(unique)} raw clusters, {(labels == -1).sum()} noise points")

    groups: dict[int, list[tuple[PRRecord, TechniqueExtraction]]] = defaultdict(list)
    for (pr, ext), label in zip(items, labels):
        if label == -1:
            continue
        groups[int(label)].append((pr, ext))

    eligible = {
        cid: g for cid, g in groups.items()
        if len(g) >= MIN_CLUSTER_PRS and len({pr.repo for pr, _ in g}) >= MIN_CLUSTER_REPOS
    }
    print(f"[cluster] {len(eligible)} clusters meet size/repo floor (of {len(groups)})")

    coherence = _verify_coherence(eligible, backend, model, timeout, workers)
    coherent = {cid: g for cid, g in eligible.items() if coherence.get(cid)}
    print(f"[cluster] {len(coherent)} confirmed coherent (of {len(eligible)})")

    surviving = {}
    for cid, g in coherent.items():
        pos, neg, passes = _consistency_stats(g)
        if passes:
            surviving[cid] = g
    print(f"[cluster] {len(surviving)} pass directional consistency (of {len(coherent)} coherent)")

    labels_by_id = _label_clusters(surviving, backend, model, timeout, workers)

    duplicate_of = _deduplicate_clusters(surviving, labels_by_id, backend, model, timeout)
    if duplicate_of:
        print(f"[cluster] {len(duplicate_of)} cluster(s) identified as duplicates of a sibling, dropping")

    result: list[NovelCluster] = []
    dropped_non_cwv = 0
    for cid, g in surviving.items():
        if cid in duplicate_of:
            continue
        info = labels_by_id.get(cid, {})
        if info.get("cwv_relevant") is not True:
            dropped_non_cwv += 1
            continue
        pos, neg, _ = _consistency_stats(g)
        pr_directions = {pr.id: d for pr, ext in g if (d := _resolve_direction(pr, ext))}
        result.append(NovelCluster(
            cluster_id=cid,
            issue_type=_slugify(info.get("issue_type") or f"novel-type-{cid}"),
            description=info.get("description", ""),
            applicable_flavors=info.get("applicable_flavors", ["eds", "cs", "ams"]),
            risk_tier=info.get("risk_tier", "medium"),
            aem_rationale=info.get("aem_rationale", ""),
            source_pr_ids=[pr.id for pr, _ in g],
            distinct_repo_count=len({pr.repo for pr, _ in g}),
            positive_count=pos, negative_count=neg,
            directional_consistency=round(max(pos, neg) / max(pos + neg, 1), 4),
            pr_directions=pr_directions,
        ))
    print(f"[cluster] {dropped_non_cwv} dropped as not CWV-relevant; {len(result)} final clusters")

    seen: dict[str, int] = {}
    result.sort(key=lambda c: len(c.source_pr_ids), reverse=True)
    for c in result:
        seen[c.issue_type] = seen.get(c.issue_type, 0) + 1
        if seen[c.issue_type] > 1:
            c.issue_type = f"{c.issue_type}-{seen[c.issue_type]}"

    return result


def write_jsonl(clusters: list[NovelCluster], path: Path) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        for c in clusters:
            f.write(json.dumps(asdict(c)) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[NovelCluster]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            out.append(NovelCluster(**json.loads(line)))
    return out
