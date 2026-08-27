"""Stage 2a: extract enrichment evidence for existing playbooks.

For each existing playbook that received triage-routed records, we pick the
top evidence PRs and separate them by direction:
  - perf_improvement → candidate "Recommended approaches" additions
  - perf_decrease    → candidate "Anti-patterns" additions

The output is not the final playbook text — that's Stage 3 (render_playbook).
This stage only selects and scores the evidence.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.triage.triage import TriageRecord

# How many PRs to pass to the generation stage per playbook per direction.
MAX_APPROACH_PRS = 5
MAX_ANTIPATTERN_PRS = 4


@dataclass
class EnrichmentEvidence:
    playbook_id: str
    approach_pr_ids: list[str] = field(default_factory=list)
    antipattern_pr_ids: list[str] = field(default_factory=list)
    approach_summaries: list[str] = field(default_factory=list)
    antipattern_summaries: list[str] = field(default_factory=list)
    approach_repo_count: int = 0
    antipattern_repo_count: int = 0


def write_jsonl(evidence: list[EnrichmentEvidence], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in evidence:
            f.write(json.dumps(asdict(e)) + "\n")


def read_jsonl(path: Path) -> list[EnrichmentEvidence]:
    items = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            items.append(EnrichmentEvidence(**json.loads(line)))
    return items


def _score_pr(pr: PRRecord) -> float:
    """Higher = more evidence-rich PR. Prefer PRs with diffs over stubs."""
    file_count = len(pr.changed_files)
    has_patch = any((f.get("patch") or "") for f in pr.changed_files)
    has_delta = pr.delta is not None
    has_title = bool(pr.title)
    return (
        file_count * 0.5
        + (3.0 if has_patch else 0.0)
        + (2.0 if has_delta else 0.0)
        + (1.0 if has_title else 0.0)
    )


def extract_enrichments(
    triage_records: list[TriageRecord],
    pr_records_by_id: dict[str, PRRecord],
) -> list[EnrichmentEvidence]:
    """Build one EnrichmentEvidence per playbook that has routed records."""

    # Group by playbook
    by_playbook: dict[str, list[TriageRecord]] = defaultdict(list)
    for tr in triage_records:
        if tr.route == "existing" and tr.playbook_id:
            by_playbook[tr.playbook_id].append(tr)

    print(f"[enrich-extract] {len(by_playbook)} playbooks have evidence")

    result = []
    for playbook_id, trs in sorted(by_playbook.items()):
        approach_trs = [
            tr for tr in trs
            if tr.signal_type == "perf_improvement"
        ]
        antipattern_trs = [
            tr for tr in trs
            if tr.signal_type == "perf_decrease"
        ]

        # Score and rank
        def ranked(trs_subset):
            scored = []
            for tr in trs_subset:
                pr = pr_records_by_id.get(tr.record_id)
                if pr:
                    scored.append((tr, pr, _score_pr(pr)))
            return sorted(scored, key=lambda x: x[2], reverse=True)

        top_approach = ranked(approach_trs)[:MAX_APPROACH_PRS]
        top_antipattern = ranked(antipattern_trs)[:MAX_ANTIPATTERN_PRS]

        ev = EnrichmentEvidence(
            playbook_id=playbook_id,
            approach_pr_ids=[pr.id for _, pr, _ in top_approach],
            antipattern_pr_ids=[pr.id for _, pr, _ in top_antipattern],
            approach_summaries=[tr.summary for tr, _, _ in top_approach],
            antipattern_summaries=[tr.summary for tr, _, _ in top_antipattern],
            approach_repo_count=len({pr.repo for _, pr, _ in top_approach}),
            antipattern_repo_count=len({pr.repo for _, pr, _ in top_antipattern}),
        )
        result.append(ev)
        print(f"  {playbook_id}: {len(top_approach)} approach PRs, "
              f"{len(top_antipattern)} anti-pattern PRs "
              f"(of {len(approach_trs)} + {len(antipattern_trs)} total routed)")

    return result
