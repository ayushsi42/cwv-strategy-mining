"""Stage 3: group extracted (perf_improvement) patterns by technique. String-
normalization clustering (lowercase, strip punctuation/whitespace) is the
primary mechanism -- deterministic and cheap, no LLM call per pattern.

An LLM-assisted near-duplicate merge pass (e.g. "lazy-load below-the-fold
images" vs "defer offscreen image loading" are the same technique) is a
documented extension point, not built for the initial demo -- clusters stay
slightly more fragmented than ideal without it, which is a precision/recall
tradeoff worth revisiting once real cluster volume justifies the extra LLM
calls.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cwv_playbook_miner.extraction.pattern_extract import ExtractedPattern


def normalize_technique(technique: str) -> str:
    t = technique.strip().lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


@dataclass
class TechniqueCluster:
    technique: str  # display name (first pattern's original casing)
    normalized_key: str
    frequency: int
    avg_delta: float | None
    framework_hints: list[str]
    applicable_signals: list[str]
    why_it_works: str
    example_code_patterns: list[str]
    example_problem_symptoms: list[str]
    source_pr_ids: list[str] = field(default_factory=list)
    distinct_repo_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    delta_p25: float | None = None
    delta_p75: float | None = None
    directional_consistency: float = 0.0
    confidence: str = "provisional"
    aliases: list[str] = field(default_factory=list)
    parent_strategy: str = ""
    cwv_metrics: list[str] = field(default_factory=list)


def cluster_patterns(patterns: list[ExtractedPattern]) -> list[TechniqueCluster]:
    groups: dict[str, list[ExtractedPattern]] = defaultdict(list)
    for p in patterns:
        groups[normalize_technique(p.technique)].append(p)

    clusters = []
    for key, items in groups.items():
        deltas = [
            abs(i.measured_delta.get("delta"))
            for i in items
            if isinstance(i.measured_delta.get("delta"), (int, float))
        ]
        clusters.append(TechniqueCluster(
            technique=items[0].technique,
            normalized_key=key,
            frequency=len(items),
            avg_delta=round(sum(deltas) / len(deltas), 2) if deltas else None,
            framework_hints=sorted({i.framework_hint for i in items}),
            applicable_signals=sorted({i.applicable_signal for i in items if i.applicable_signal}),
            why_it_works=items[0].why_it_works,
            example_code_patterns=[i.code_pattern for i in items[:3]],
            example_problem_symptoms=[i.problem_symptom for i in items[:3]],
            source_pr_ids=[i.source_id for i in items],
        ))
    return sorted(clusters, key=lambda c: c.frequency, reverse=True)


def merge_clusters(clusters: list[TechniqueCluster]) -> TechniqueCluster:
    """Combines multiple distinct technique clusters that stage-4 classified
    to the SAME target_issue_type (e.g. two different mined techniques both
    enrich `js-execution`) into one, so stage 6 grounds a single candidate
    file in all of them instead of the second silently overwriting the
    first's rendered file."""
    if len(clusters) == 1:
        return clusters[0]
    return TechniqueCluster(
        technique=" + ".join(c.technique for c in clusters),
        normalized_key=clusters[0].normalized_key,
        frequency=sum(c.frequency for c in clusters),
        avg_delta=round(sum((c.avg_delta or 0) for c in clusters) / len(clusters), 2),
        framework_hints=sorted({h for c in clusters for h in c.framework_hints}),
        applicable_signals=sorted({s for c in clusters for s in c.applicable_signals}),
        why_it_works=" | ".join(c.why_it_works for c in clusters if c.why_it_works),
        example_code_patterns=[p for c in clusters for p in c.example_code_patterns],
        example_problem_symptoms=[s for c in clusters for s in c.example_problem_symptoms],
        source_pr_ids=[pid for c in clusters for pid in c.source_pr_ids],
        distinct_repo_count=len({pid.rsplit("#", 1)[0] for c in clusters for pid in c.source_pr_ids}),
        positive_count=sum(c.positive_count for c in clusters),
        negative_count=sum(c.negative_count for c in clusters),
        delta_p25=None,
        delta_p75=None,
        directional_consistency=round(
            sum(c.positive_count for c in clusters)
            / max(1, sum(c.positive_count + c.negative_count for c in clusters)), 4,
        ),
        confidence=min(
            (c.confidence for c in clusters),
            key={"provisional": 0, "medium": 1, "high": 2}.get,
            default="provisional",
        ),
        aliases=sorted({alias for c in clusters for alias in c.aliases}),
        parent_strategy=clusters[0].parent_strategy,
        cwv_metrics=sorted({metric for c in clusters for metric in c.cwv_metrics}),
    )


def write_jsonl(clusters: list[TechniqueCluster], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in clusters:
            f.write(json.dumps(asdict(c)) + "\n")


def read_jsonl(path: Path) -> list[TechniqueCluster]:
    clusters = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            clusters.append(TechniqueCluster(**json.loads(line)))
    return clusters
