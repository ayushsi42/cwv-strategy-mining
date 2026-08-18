"""Stage 4: decide whether a measured technique is useful CWV guidance.

The classifier is deliberately platform-neutral. It judges performance
relevance, evidence quality, and duplication within the mined technique set;
it does not translate techniques to a CMS, framework, or delivery flavor.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwv_playbook_miner.extraction.cluster import TechniqueCluster
from cwv_playbook_miner.llm.client import LLMError, complete_json


SYSTEM_PROMPT = """You review techniques mined from real pull requests with measured web-performance changes.

Keep a cluster only when the changed code and explanation support a reusable page-performance technique. Drop incidental correlations, build-time-only improvements with no delivered-page effect, social-preview-only work, vague refactors, and duplicates that add no distinct mechanism.

Do not translate the technique to another platform or framework. Do not invent implementation details absent from the supplied evidence.

Return strict JSON:
{
  "action": "candidate" | "drop",
  "action_reason": "<=2 sentences grounded only in the supplied evidence",
  "risk_tier_guess": "low" | "medium" | "high"
}

Use "candidate" when the evidence supports useful generic CWV guidance. Use "drop" when it does not."""


def build_prompt(cluster: TechniqueCluster) -> str:
    return f"""Canonical technique ID (already assigned; do not rename): {cluster.normalized_key}
Parent strategy: {cluster.parent_strategy}
Sub-strategy: {cluster.technique}
Measured in {cluster.frequency} real PR(s): {', '.join(cluster.source_pr_ids)}
Independent repositories: {cluster.distinct_repo_count}
Evidence direction: {cluster.positive_count} improvements / {cluster.negative_count} regressions
Directional consistency: {cluster.directional_consistency:.1%}
Absolute delta distribution: p25={cluster.delta_p25}, median={cluster.avg_delta}, p75={cluster.delta_p75}
Aggregation confidence: {cluster.confidence}
Known aliases: {', '.join(cluster.aliases)}
Why it works: {cluster.why_it_works}
Framework hints from source: {', '.join(cluster.framework_hints)}
Audit signals: {', '.join(cluster.applicable_signals)}
Code patterns from source:
{chr(10).join('- ' + value for value in cluster.example_code_patterns)}
Problem symptoms from source:
{chr(10).join('- ' + value for value in cluster.example_problem_symptoms)}

Return the JSON decision."""


@dataclass
class Classification:
    normalized_key: str
    technique: str
    action: str
    target_issue_type: str
    action_reason: str
    risk_tier_guess: str

    @property
    def survives(self) -> bool:
        return self.action == "candidate"


def classify_cluster(
    cluster: TechniqueCluster, backend: str, model: str | None, timeout: int,
) -> Classification | None:
    try:
        result = complete_json(
            SYSTEM_PROMPT, build_prompt(cluster), backend=backend, model=model, timeout=timeout,
        )
    except LLMError:
        return None
    action = result.get("action", "drop")
    return Classification(
        normalized_key=cluster.normalized_key,
        technique=cluster.technique,
        action=action if action in {"candidate", "drop"} else "drop",
        # Candidate filenames use the persistent aggregate ID, never a fresh
        # LLM-generated slug that could drift across runs.
        target_issue_type=cluster.normalized_key,
        action_reason=result.get("action_reason", ""),
        risk_tier_guess=result.get("risk_tier_guess", "medium"),
    )


def classify_clusters(
    clusters: list[TechniqueCluster], backend: str, model: str | None, timeout: int,
) -> list[Classification]:
    results = []
    for index, cluster in enumerate(clusters, 1):
        classification = classify_cluster(cluster, backend, model, timeout)
        if classification:
            results.append(classification)
            print(
                f"  [{index}/{len(clusters)}] {cluster.technique!r}: "
                f"{classification.action} -> {classification.target_issue_type}"
            )
        else:
            print(f"  [{index}/{len(clusters)}] {cluster.technique!r}: classification failed, skipped")
    return results


def write_jsonl(classifications: list[Classification], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for classification in classifications:
            handle.write(json.dumps(asdict(classification)) + "\n")
