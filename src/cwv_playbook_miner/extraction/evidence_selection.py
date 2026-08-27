"""Shared evidence-quality scoring + repo-diversity cap, used by both
enrich_extract.py (existing-playbook evidence) and generation/
render_playbook.py (new-cluster evidence) so the two paths can't drift
into inconsistent selection rules."""

from __future__ import annotations

from collections import defaultdict

from cwv_playbook_miner.extraction.pr_record import PRRecord

MAX_PER_REPO = 2


def score(pr: PRRecord) -> float:
    file_count = len(pr.changed_files)
    has_patch = any((f.get("patch") or "") for f in pr.changed_files)
    has_delta = pr.delta is not None
    has_title = bool(pr.title)
    return file_count * 0.5 + (3.0 if has_patch else 0.0) + (2.0 if has_delta else 0.0) + (1.0 if has_title else 0.0)


def select_diverse(candidates: list[PRRecord], limit: int, max_per_repo: int = MAX_PER_REPO) -> list[PRRecord]:
    """Rank by evidence quality, but cap repeats from the same repo so one
    codebase's habit can't crowd out the rest -- fill remaining slots from
    already-represented repos only after every repo has had a fair shot."""
    ranked = sorted(candidates, key=score, reverse=True)
    selected: list[PRRecord] = []
    per_repo: dict[str, int] = defaultdict(int)
    leftover: list[PRRecord] = []
    for pr in ranked:
        if len(selected) >= limit:
            break
        if per_repo[pr.repo] < max_per_repo:
            selected.append(pr)
            per_repo[pr.repo] += 1
        else:
            leftover.append(pr)
    for pr in leftover:
        if len(selected) >= limit:
            break
        selected.append(pr)
    return selected
