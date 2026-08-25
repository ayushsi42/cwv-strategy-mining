"""The record shape stages 2+ consume -- deliberately similar in spirit to
smol-planner's `cwv_pr_context.py` record shape (id, repo, signal_type,
metrics, changed_files with patches) since stages 2+ here play the same role
its `cwv_pattern_mining.py` extract stage does.

Two real input channels feed this shape:
  - our own live GH Archive mining (sourcing/gharchive_mine.py + labeling/) --
    `source="gharchive_live"`
  - a real, pre-mined external corpus (extraction/external_corpus.py), used
    because live mining's own perf_improvement yield was confirmed near-zero
    over ~52 real scanned days (see docs/pipeline-design.md) -- `source`
    identifies exactly which external dataset/file a record came from, so
    provenance stays traceable per Julien's "note which source PR(s) each
    candidate is grounded in."
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class PRRecord:
    id: str  # "{repo}#{pr_number}"
    repo: str
    pr_number: int
    signal_type: str  # perf_improvement | perf_decrease | perf_flagged
    metric_key: str | None
    before: float | None
    after: float | None
    delta: float | None
    title: str | None = None
    pr_body_markdown: str | None = None
    changed_files: list[dict] = field(default_factory=list)  # [{filename, patch}]
    template_names: list[str] = field(default_factory=list)
    source: str = "gharchive_live"
    # Only set for signal_type == "perf_flagged": the review/review-comment
    # body that triggered discovery (no structured bot template matched it,
    # so metric_key/before/after/delta stay None -- extraction infers
    # relevance and direction from this text plus the diff. See
    # gharchive_mine.human_flagged_candidates and
    # pattern_extract.py's inferred_signal_type.
    human_signal_text: str | None = None


def write_jsonl(records: list[PRRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


def read_jsonl(path: Path) -> list[PRRecord]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            records.append(PRRecord(**json.loads(line)))
    return records
