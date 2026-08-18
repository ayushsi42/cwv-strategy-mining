"""Stage 5: for each surviving generic CWV cluster, pull
matching perf_decrease-labeled patterns as anti-pattern grounding -- Julien's
"pull the matching perf_decrease clusters for the Anti-patterns side of the
same issue types" instruction.

Matching is normalized-technique-key overlap first (same clustering key as
stage 3), falling back to applicable_signal keyword overlap when no exact
technique match exists -- a perf_decrease PR that regressed via "adding a
render-blocking third-party script" is a valid anti-pattern for an
"defer non-critical third-party scripts" recommended-approach cluster even
though the technique names don't normalize identically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from cwv_playbook_miner.extraction.cluster import normalize_technique
from cwv_playbook_miner.extraction.pattern_extract import ExtractedPattern


@dataclass
class AntiPatternMatch:
    cluster_key: str
    source_id: str
    source_repo: str
    technique: str
    problem_symptom: str
    code_pattern: str
    why_it_works: str
    measured_delta: dict = field(default_factory=dict)


def _signal_tokens(signal: str) -> set[str]:
    return {t for t in normalize_technique(signal).split() if len(t) > 3}


def pull_antipatterns(
    cluster_key: str, cluster_signals: list[str], decrease_patterns: list[ExtractedPattern],
) -> list[AntiPatternMatch]:
    exact = [p for p in decrease_patterns if normalize_technique(p.technique) == cluster_key]
    if exact:
        matches = exact
    else:
        cluster_tokens = set()
        for s in cluster_signals:
            cluster_tokens |= _signal_tokens(s)
        matches = [
            p for p in decrease_patterns
            if cluster_tokens & (_signal_tokens(p.applicable_signal) | _signal_tokens(p.problem_symptom))
        ]

    return [
        AntiPatternMatch(
            cluster_key=cluster_key, source_id=p.source_id, source_repo=p.source_repo,
            technique=p.technique, problem_symptom=p.problem_symptom, code_pattern=p.code_pattern,
            why_it_works=p.why_it_works, measured_delta=p.measured_delta,
        )
        for p in matches[:3]  # cap -- generation only needs a couple of grounding examples
    ]


def write_jsonl(matches: list[AntiPatternMatch], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps(asdict(m)) + "\n")
