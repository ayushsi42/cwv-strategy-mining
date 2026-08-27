"""Stage 1 orchestrator: summarise → embed → route.

Reads all three source JSONL files, produces `triage.jsonl` where each record
carries its routing decision (existing playbook id, novel, or drop) plus the
technique summary used to make that decision.

The output is the sole input to Stage 2a (enrich_extract) and Stage 2b
(semantic_cluster); downstream stages never touch the raw PR records again
for routing decisions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord, read_jsonl as read_pr_jsonl
from cwv_playbook_miner.triage.summarize import TriageSummary, summarize_records
from cwv_playbook_miner.triage.embed import (
    embed_playbooks,
    route_summaries,
    disambiguate_ambiguous,
)


@dataclass
class TriageRecord:
    record_id: str
    signal_type: str            # perf_improvement | perf_decrease | perf_flagged
    summary: str                # LLM-generated technique phrase (or "DROP")
    route: str                  # "existing" | "novel" | "drop"
    playbook_id: str | None     # set when route == "existing"
    similarity_score: float     # cosine sim to nearest playbook (0.0 if drop/novel)
    repo: str = ""


def write_triage_jsonl(records: list[TriageRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


def read_triage_jsonl(path: Path) -> list[TriageRecord]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            records.append(TriageRecord(**json.loads(line)))
    return records


def run_triage(
    source_paths: list[Path],
    handoff_dir: Path,
    *,
    backend: str = "openai",
    model: str | None = None,
    embed_provider: str = "openai",
    embed_model: str | None = None,
    embed_base_url: str | None = None,
    summarize_workers: int = 8,
    timeout: int = 120,
    cache_dir: Path | None = None,
    high_threshold: float = 0.78,
    low_threshold: float = 0.45,
) -> list[TriageRecord]:
    """Full Stage 1 pipeline. Returns one TriageRecord per source PR record."""

    # 1. Load all source records
    all_records: list[PRRecord] = []
    for path in source_paths:
        if path.exists():
            all_records.extend(read_pr_jsonl(path))
    print(f"[triage] loaded {len(all_records)} source records from {len(source_paths)} files")

    # 2. LLM compact summaries (cached)
    summaries: list[TriageSummary] = summarize_records(
        all_records,
        backend=backend,
        model=model,
        timeout=timeout,
        workers=summarize_workers,
        cache_dir=cache_dir,
    )
    summary_by_id = {s.record_id: s for s in summaries}

    # 3. Embed existing playbooks
    embed_kwargs = dict(
        provider=embed_provider,
        model=embed_model,
        base_url=embed_base_url,
    )
    print(f"[triage] embedding {handoff_dir} playbooks...")
    playbook_embeddings = embed_playbooks(handoff_dir, **embed_kwargs)
    print(f"[triage] embedded {len(playbook_embeddings)} existing playbooks")

    # 4. Separate drops, then route the rest
    non_drop_records: list[PRRecord] = []
    non_drop_summaries: list[str] = []

    triage_records: list[TriageRecord] = []
    record_by_id = {r.id: r for r in all_records}

    for record in all_records:
        ts = summary_by_id.get(record.id)
        if ts is None or ts.is_drop:
            triage_records.append(TriageRecord(
                record_id=record.id,
                signal_type=record.signal_type,
                summary=ts.summary if ts else "DROP",
                route="drop",
                playbook_id=None,
                similarity_score=0.0,
                repo=record.repo,
            ))
        else:
            non_drop_records.append(record)
            non_drop_summaries.append(ts.summary)

    print(f"[triage] {len(triage_records)} drops, {len(non_drop_records)} to embed+route")

    if not non_drop_records:
        return triage_records

    # 5. Cosine routing
    routes = route_summaries(
        non_drop_summaries,
        playbook_embeddings,
        high_threshold=high_threshold,
        low_threshold=low_threshold,
        **embed_kwargs,
    )

    # 6. Disambiguate ambiguous band with LLM
    ambiguous_indices = [i for i, (route, _, _) in enumerate(routes) if route == "ambiguous"]
    if ambiguous_indices:
        print(f"[triage] disambiguating {len(ambiguous_indices)} ambiguous summaries via LLM")
        # Build playbook descriptions from their embeddings (keys only — descriptions
        # come from the playbook content read in embed_playbooks, use filenames as
        # readable labels here since we don't store the descriptions).
        playbook_descs = {pid: pid.replace("-", " ") for pid in playbook_embeddings}
        amb_summaries = [non_drop_summaries[i] for i in ambiguous_indices]
        amb_candidates = [routes[i][1] for i in ambiguous_indices]  # nearest playbook
        resolved = disambiguate_ambiguous(
            amb_summaries,
            list(playbook_embeddings.keys()),
            playbook_descs,
            backend=backend,
            model=model,
            timeout=timeout,
        )
        for j, idx in enumerate(ambiguous_indices):
            resolved_route, resolved_pid = resolved[j]
            routes[idx] = (resolved_route, resolved_pid, routes[idx][2])

    # 7. Assemble final triage records
    for i, record in enumerate(non_drop_records):
        route, playbook_id, score = routes[i]
        ts = summary_by_id[record.id]
        triage_records.append(TriageRecord(
            record_id=record.id,
            signal_type=record.signal_type,
            summary=ts.summary,
            route=route,
            playbook_id=playbook_id,
            similarity_score=round(score, 4),
            repo=record.repo,
        ))

    # Stats
    by_route: dict[str, int] = {}
    by_playbook: dict[str, int] = {}
    for tr in triage_records:
        by_route[tr.route] = by_route.get(tr.route, 0) + 1
        if tr.playbook_id:
            by_playbook[tr.playbook_id] = by_playbook.get(tr.playbook_id, 0) + 1

    print(f"[triage] routing complete: {by_route}")
    if by_playbook:
        top = sorted(by_playbook.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"[triage] top existing-playbook assignments: {top}")

    return triage_records
