"""The record shape every downstream stage consumes: `id`, `repo`,
`signal_type`, metrics, `changed_files` with patches, plus everything
`enrichment/pr_text.py` backfills (title, body, comments/reviews) since GH
Archive's free event stream never carries those. Written by `sourcing/` +
`labeling/` (stage 0), read by every stage after it."""

from __future__ import annotations

import json
import os
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
    # ISO 8601 PR merge timestamp -- the temporal dimension needed for any
    # cross-year/trend analysis over the mined dataset. None only for
    # records where the merge event/API response genuinely didn't carry one
    # (should be rare/never for gharchive_live records; external-corpus
    # records may not have it depending on the source dataset).
    merged_at: str | None = None
    # Only set for signal_type == "perf_flagged": the review/review-comment
    # body that triggered discovery (no structured bot template matched it,
    # so metric_key/before/after/delta stay None -- extraction infers
    # relevance and direction from this text plus the diff. See
    # gharchive_mine.human_flagged_candidates and
    # pattern_extract.py's inferred_signal_type.
    human_signal_text: str | None = None
    # Backfilled via enrichment/pr_text.py (GitHub GraphQL) -- title/body
    # aren't in GH Archive's free PullRequestEvent stream, so these stay
    # None until that stage runs. pr_comments holds every issue comment,
    # review, and inline review comment: [{"kind": "issue_comment"|"review"|
    # "review_comment", "author", "body", "created_at", "state", "path"}].
    # text_truncated is set when a PR had more comments/reviews than the
    # fetch page size, so it can't silently look "complete" -- same class of
    # gap the changed_files 30-file GH API cap turned out to be.
    pr_comments: list[dict] = field(default_factory=list)
    text_enriched: bool = False
    text_truncated: bool = False


def write_jsonl(records: list[PRRecord], path: Path) -> None:
    """Writes via a temp file + atomic rename so a concurrent reader (or a
    crash mid-write) never sees a half-written file -- this file has
    historically been rewritten whole on every backfill chunk, and a plain
    in-place open("w") is exactly what caused a reader to catch it
    mid-truncation once already."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[PRRecord]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            records.append(PRRecord(**json.loads(line)))
    return records
