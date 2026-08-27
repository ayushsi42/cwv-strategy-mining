"""Stage 5a: existing-playbook evidence selection, diversity-weighted --
caps how many PRs from a single repo can count as evidence (the EDA found
ant-design's two repos alone were 39-54% of all bot-matched evidence, which
would otherwise let one org's repeated pattern single-handedly validate or
invalidate a technique). Built on routing.py's RoutingRecord (LLM-verified
matches, never a bare threshold)."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.extraction.technique_extract import TechniqueExtraction
from cwv_playbook_miner.extraction.evidence_selection import select_diverse
from cwv_playbook_miner.routing.route import RoutingRecord

MAX_APPROACH_PRS = 5
MAX_ANTIPATTERN_PRS = 4


@dataclass
class EnrichmentEvidence:
    playbook_id: str
    approach_pr_ids: list[str] = field(default_factory=list)
    antipattern_pr_ids: list[str] = field(default_factory=list)
    approach_repo_count: int = 0
    antipattern_repo_count: int = 0


def _resolve_direction(record: PRRecord, extraction: TechniqueExtraction) -> str | None:
    if record.signal_type == "perf_improvement":
        return "positive"
    if record.signal_type == "perf_decrease":
        return "negative"
    if record.signal_type == "perf_flagged" and extraction.direction in ("positive", "negative"):
        return extraction.direction
    return None


def extract_enrichments(
    routing_records: list[RoutingRecord],
    pr_by_id: dict[str, PRRecord],
    extraction_by_id: dict[str, TechniqueExtraction],
) -> list[EnrichmentEvidence]:
    by_playbook: dict[str, list[RoutingRecord]] = defaultdict(list)
    for r in routing_records:
        if r.route == "existing" and r.playbook_id:
            by_playbook[r.playbook_id].append(r)

    print(f"[enrich-extract] {len(by_playbook)} playbooks have evidence")

    result = []
    for playbook_id, routes in sorted(by_playbook.items()):
        approach_prs, antipattern_prs = [], []
        for r in routes:
            pr = pr_by_id.get(r.record_id)
            ext = extraction_by_id.get(r.record_id)
            if not pr or not ext:
                continue
            direction = _resolve_direction(pr, ext)
            if direction == "positive":
                approach_prs.append(pr)
            elif direction == "negative":
                antipattern_prs.append(pr)

        top_approach = select_diverse(approach_prs, MAX_APPROACH_PRS)
        top_antipattern = select_diverse(antipattern_prs, MAX_ANTIPATTERN_PRS)

        result.append(EnrichmentEvidence(
            playbook_id=playbook_id,
            approach_pr_ids=[pr.id for pr in top_approach],
            antipattern_pr_ids=[pr.id for pr in top_antipattern],
            approach_repo_count=len({pr.repo for pr in top_approach}),
            antipattern_repo_count=len({pr.repo for pr in top_antipattern}),
        ))
        print(f"  {playbook_id}: {len(top_approach)} approach PRs ({len({pr.repo for pr in top_approach})} repos), "
              f"{len(top_antipattern)} anti-pattern PRs (of {len(approach_prs)} + {len(antipattern_prs)} total)")

    return result


def write_jsonl(evidence: list[EnrichmentEvidence], path: Path) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        for e in evidence:
            f.write(json.dumps(asdict(e)) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[EnrichmentEvidence]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            out.append(EnrichmentEvidence(**json.loads(line)))
    return out
