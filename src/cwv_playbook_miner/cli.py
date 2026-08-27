"""CLI entrypoint. Subcommands mirror the pipeline stages 0-6 from the plan;
`run-all` chains them with sensible default paths under `data/`. Every
subcommand reads/writes JSONL so intermediate output stays inspectable
(`cat data/processed/.../*.jsonl | jq`), same "each stage is a standalone,
debuggable step" philosophy as smol-planner's own dataset scripts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from cwv_playbook_miner.antipatterns.pull_antipatterns import pull_antipatterns
from cwv_playbook_miner.antipatterns import pull_antipatterns as antipatterns_mod
from cwv_playbook_miner.classification.classify_cluster import Classification, classify_clusters
from cwv_playbook_miner.classification import classify_cluster as classify_mod
from cwv_playbook_miner.aggregation.statistical import (
    aggregate_patterns,
    read_aggregates,
    resolve_substrategy_matches,
    to_technique_cluster,
    write_aggregates,
)
from cwv_playbook_miner.extraction import cluster as cluster_mod
from cwv_playbook_miner.extraction import pattern_extract
from cwv_playbook_miner.extraction.external_corpus import load_golden_perf_improvement
from cwv_playbook_miner.extraction.pr_record import PRRecord, read_jsonl as read_pr_jsonl, write_jsonl as write_pr_jsonl
from cwv_playbook_miner.taxonomy import write_parent_proposals
from cwv_playbook_miner.generation.render_candidate import render_candidate, write_candidate
from cwv_playbook_miner.llm.client import resolve_default_backend
from cwv_playbook_miner.sourcing.gharchive_fetch import read_cursor, write_cursor
from cwv_playbook_miner.sourcing.gharchive_mine import (
    check_pr_merged, fetch_pr_comments, fetch_pr_diff, human_flagged_candidates, is_ci_docs_only,
    scan_range, touches_frontend,
)
from cwv_playbook_miner.labeling.signal_label import label_scan_result

DATA_RAW = Path("data/raw")
DATA_PROCESSED = Path("data/processed")
CURSOR_PATH = DATA_RAW / "gharchive_cursor.json"
CANDIDATES_DIR = Path("candidates")


def _add_llm_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend", default=None, help="openai (default, requires OPENAI_API_KEY) | claude-cli | openai-compatible")
    p.add_argument("--model", default=None)
    p.add_argument("--timeout", type=int, default=120)


def _resolve_start(args: argparse.Namespace) -> datetime:
    if args.start:
        return datetime.fromisoformat(args.start)
    if not args.use_cursor:
        raise SystemExit("--start is required unless --use-cursor is set and a cursor file already exists")
    cursor = read_cursor(CURSOR_PATH)
    if cursor is None:
        raise SystemExit(f"--use-cursor set but no cursor file yet at {CURSOR_PATH} -- pass --start for the first run")
    return cursor + timedelta(hours=1)  # resume just past the last fully-scanned hour


def cmd_source(args: argparse.Namespace) -> None:
    start = _resolve_start(args)
    end = datetime.fromisoformat(args.end) if args.end else start + timedelta(hours=args.hours)

    print(f"Scanning GH Archive {start.isoformat()} -> {end.isoformat()} "
          f"({int((end - start).total_seconds() // 3600)} hours)...")

    def progress(dt, result):
        if result.hours_scanned % 5 == 0:
            print(f"  ...{result.hours_scanned} hours scanned, "
                  f"{len(result.comment_hits)} comment hits, {len(result.merged_prs)} merges seen so far")

    # Persisting a cursor before this command writes its records can lose data
    # after interruption. The bounded backfill command checkpoints only after
    # each completed chunk instead.
    result = scan_range(
        start, end, on_progress=progress,
        track_merges=not getattr(args, "comment_only", False),
        workers=getattr(args, "workers", 1),
    )
    print(f"Scan done: {result.hours_scanned} hours scanned ({result.hours_skipped} skipped/unpublished), "
          f"{len(result.comment_hits)} bot-comment hits, {len(result.merged_prs)} merged PRs seen, "
          f"{len(result.free_candidates)} candidates clear BOTH free filters in-window.")

    labeled = label_scan_result(result.comment_hits)
    labeled_by_pr = {(pr.repo, pr.pr_number): pr for pr in labeled}
    tier_a = [pr for pr in labeled if pr.tier == "A"]
    print(f"  structural fingerprinting: {len(labeled)} broad PR hit(s) -> {len(tier_a)} Tier-A PR(s)")

    # A single Tier-A comment in-window is promising but not enough for a
    # delta. Pull full history only for structurally verified reports, before
    # spending merge-status calls on broad keyword hits.
    unresolved = [lp for lp in tier_a if lp.signal_type == "unlabeled"]

    def resolve_full_history(lp):
        repo, pr_number = lp.repo, lp.pr_number
        full_comments = fetch_pr_comments(repo, pr_number)
        if len(full_comments) <= lp.n_comments_seen:
            return lp
        from cwv_playbook_miner.labeling.signal_label import label_pr
        return label_pr(repo, pr_number, full_comments)

    if unresolved:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        print(
            f"  resolving full comment history for {len(unresolved)} Tier-A PR(s) "
            f"with {getattr(args, 'api_workers', 1)} worker(s)..."
        )
        with ThreadPoolExecutor(max_workers=getattr(args, "api_workers", 1)) as pool:
            futures = {pool.submit(resolve_full_history, lp): lp for lp in unresolved}
            for future in as_completed(futures):
                original = futures[future]
                relabeled = future.result()
                repo, pr_number = original.repo, original.pr_number
                labeled_by_pr[(repo, pr_number)] = relabeled
                if relabeled.signal_type != "unlabeled":
                    print(f"    resolved: {relabeled.signal_type} ({relabeled.metric_key} "
                          f"{relabeled.before} -> {relabeled.after}, delta={relabeled.delta})")

    measurable = {
        key for key, lp in labeled_by_pr.items()
        if lp.signal_type in ("perf_improvement", "perf_decrease")
    }
    in_window_merged = measurable & set(result.merged_prs)
    merged_at_by_pr: dict[tuple[str, int], str | None] = {
        key: result.merged_prs[key].get("merged_at") for key in in_window_merged
    }
    fallback_confirmed = []
    for repo, pr_number in sorted(measurable - in_window_merged):
        merged_at = check_pr_merged(repo, pr_number)
        if merged_at:
            fallback_confirmed.append((repo, pr_number))
            merged_at_by_pr[(repo, pr_number)] = merged_at
    candidates = sorted(in_window_merged | set(fallback_confirmed))
    print(
        f"  {len(measurable)} measurable PR(s), {len(candidates)} confirmed merged "
        f"({len(fallback_confirmed)} via fallback check)"
    )

    perf_improvement: list[PRRecord] = []
    perf_decrease: list[PRRecord] = []
    for repo, pr_number in candidates:
        lp = labeled_by_pr.get((repo, pr_number))
        if lp is None or lp.signal_type not in ("perf_improvement", "perf_decrease"):
            continue
        print(f"  fetching diff for {repo}#{pr_number} ({lp.signal_type}, {lp.metric_key} delta={lp.delta})...")
        changed_files = fetch_pr_diff(repo, pr_number)
        if changed_files is None:
            print("    skipped (diff fetch failed)")
            continue
        if is_ci_docs_only(changed_files):
            print("    skipped (CI/docs-only diff)")
            continue
        if not touches_frontend(changed_files):
            print("    skipped (no frontend files touched)")
            continue
        record = PRRecord(
            id=f"{repo}#{pr_number}", repo=repo, pr_number=pr_number, signal_type=lp.signal_type,
            metric_key=lp.metric_key, before=lp.before, after=lp.after, delta=lp.delta,
            changed_files=changed_files, template_names=lp.template_names,
            merged_at=merged_at_by_pr.get((repo, pr_number)),
        )
        (perf_improvement if lp.signal_type == "perf_improvement" else perf_decrease).append(record)

    # Human-flagged (non-bot review / inline review comment) candidates: no
    # structured bot template ever matches prose (registry.py's
    # generic_fallback always returns tier B, no parsed delta), so these
    # never reach `measurable` above -- they're a separate, unquantified
    # discovery signal. Extraction (stage 2) infers relevance and direction
    # from the diff + the flagging comment's text; see
    # pattern_extract.py's inferred_signal_type.
    flagged = human_flagged_candidates(result.comment_hits) - measurable
    flagged_in_window = flagged & set(result.merged_prs)
    for key in flagged_in_window:
        merged_at_by_pr.setdefault(key, result.merged_prs[key].get("merged_at"))
    flagged_fallback_confirmed = []
    for repo, pr_number in sorted(flagged - flagged_in_window):
        merged_at = check_pr_merged(repo, pr_number)
        if merged_at:
            flagged_fallback_confirmed.append((repo, pr_number))
            merged_at_by_pr.setdefault((repo, pr_number), merged_at)
    flagged_merged = sorted(flagged_in_window | set(flagged_fallback_confirmed))
    if flagged:
        print(
            f"  {len(flagged)} human-flagged PR(s) (non-bot review/review-comment), "
            f"{len(flagged_merged)} confirmed merged"
        )

    hit_by_flagged_pr = {
        (h.repo, h.pr_number): h for h in result.comment_hits if h.source in ("review", "review_comment")
    }
    perf_flagged: list[PRRecord] = []
    for repo, pr_number in flagged_merged:
        print(f"  fetching diff for {repo}#{pr_number} (perf_flagged, human-signal candidate)...")
        changed_files = fetch_pr_diff(repo, pr_number)
        if changed_files is None:
            print("    skipped (diff fetch failed)")
            continue
        if is_ci_docs_only(changed_files):
            print("    skipped (CI/docs-only diff)")
            continue
        if not touches_frontend(changed_files):
            print("    skipped (no frontend files touched)")
            continue
        hit = hit_by_flagged_pr.get((repo, pr_number))
        perf_flagged.append(PRRecord(
            id=f"{repo}#{pr_number}", repo=repo, pr_number=pr_number, signal_type="perf_flagged",
            metric_key=None, before=None, after=None, delta=None,
            changed_files=changed_files, human_signal_text=hit.body if hit else None,
            merged_at=merged_at_by_pr.get((repo, pr_number)),
        ))

    if getattr(args, "append", False):
        for records, filename in (
            (perf_improvement, "perf_improvement.jsonl"),
            (perf_decrease, "perf_decrease.jsonl"),
            (perf_flagged, "perf_flagged.jsonl"),
        ):
            path = DATA_PROCESSED / filename
            existing = read_pr_jsonl(path) if path.exists() and path.stat().st_size else []
            by_id = {record.id: record for record in existing}
            by_id.update({record.id: record for record in records})
            write_pr_jsonl(list(by_id.values()), path)
    else:
        write_pr_jsonl(perf_improvement, DATA_PROCESSED / "perf_improvement.jsonl")
        write_pr_jsonl(perf_decrease, DATA_PROCESSED / "perf_decrease.jsonl")
        write_pr_jsonl(perf_flagged, DATA_PROCESSED / "perf_flagged.jsonl")
    print(f"Wrote {len(perf_improvement)} perf_improvement + {len(perf_decrease)} perf_decrease + "
          f"{len(perf_flagged)} perf_flagged records to {DATA_PROCESSED}/")
    if getattr(args, "use_cursor", False):
        write_cursor(CURSOR_PATH, end - timedelta(hours=1))


def cmd_backfill(args: argparse.Namespace) -> None:
    """Run a long GH Archive sweep in durable, bounded chunks."""
    if args.start:
        start = datetime.fromisoformat(args.start)
    else:
        cursor = read_cursor(CURSOR_PATH)
        if cursor is None:
            raise SystemExit("--start is required for the first backfill run")
        start = cursor + timedelta(hours=1)
    end = datetime.fromisoformat(args.end)
    current = start
    chunk_number = 0
    while current < end:
        chunk_end = min(current + timedelta(hours=args.chunk_hours), end)
        chunk_number += 1
        print(f"\n=== backfill chunk {chunk_number}: {current.isoformat()} -> {chunk_end.isoformat()} ===")
        chunk_args = argparse.Namespace(
            start=current.isoformat(), end=chunk_end.isoformat(), hours=args.chunk_hours,
            use_cursor=False, append=True, comment_only=True,
            workers=args.workers, api_workers=args.api_workers,
        )
        cmd_source(chunk_args)
        write_cursor(CURSOR_PATH, chunk_end - timedelta(hours=1))
        print(f"Checkpointed completed hour {chunk_end - timedelta(hours=1)}")
        current = chunk_end
    print(f"Backfill complete through {end.isoformat()}")


def cmd_import_external(args: argparse.Namespace) -> None:
    print(f"Loading external corpus (min_perf_delta={args.min_delta}, limit={args.limit})...")
    external = load_golden_perf_improvement(min_perf_delta=args.min_delta, limit=args.limit)
    print(f"  {len(external)} real perf_improvement record(s) from Ayush-Singh/cwv-planner-dataset-v1")

    path = DATA_PROCESSED / "perf_improvement.jsonl"
    existing = read_pr_jsonl(path) if path.exists() and path.stat().st_size > 0 else []
    existing_ids = {r.id for r in existing}
    merged = existing + [r for r in external if r.id not in existing_ids]
    write_pr_jsonl(merged, path)
    print(f"Wrote {len(merged)} total perf_improvement record(s) ({len(existing)} live-mined + "
          f"{len(merged) - len(existing)} new external) -> {path}")


def cmd_extract(args: argparse.Namespace) -> None:
    backend = args.backend or resolve_default_backend()
    input_path = DATA_PROCESSED / f"{args.signal_type}.jsonl"
    records = read_pr_jsonl(input_path)
    print(f"Extracting patterns from {len(records)} {args.signal_type} record(s) via backend={backend} "
          f"(batch_size={args.batch_size}, concurrency={args.concurrency})...")
    patterns = pattern_extract.extract_patterns(
        records, backend, args.model, args.timeout, args.concurrency, args.batch_size,
    )
    out_path = DATA_PROCESSED / f"{args.signal_type}.patterns.jsonl"
    pattern_extract.write_jsonl(patterns, out_path)
    print(f"Wrote {len(patterns)} extracted patterns -> {out_path}")


def cmd_cluster(args: argparse.Namespace) -> None:
    improvement_patterns = pattern_extract.read_jsonl(DATA_PROCESSED / "perf_improvement.patterns.jsonl")
    decrease_path = DATA_PROCESSED / "perf_decrease.patterns.jsonl"
    decrease_patterns = pattern_extract.read_jsonl(decrease_path) if decrease_path.exists() else []
    flagged_path = DATA_PROCESSED / "perf_flagged.patterns.jsonl"
    flagged_patterns = pattern_extract.read_jsonl(flagged_path) if flagged_path.exists() else []
    patterns = improvement_patterns + decrease_patterns + flagged_patterns
    aggregate_path = DATA_PROCESSED / "technique_aggregates.jsonl"
    prior = [] if getattr(args, "rebuild_registry", False) else read_aggregates(aggregate_path)
    if getattr(args, "rebuild_registry", False):
        print("  rebuilding child registry from extracted observations (prior aliases ignored)")
    if not args.no_llm_merge:
        backend = args.backend or resolve_default_backend()
        resolve_substrategy_matches(patterns, prior, backend, args.model, args.timeout)
    proposal_count = write_parent_proposals(
        patterns, DATA_PROCESSED / "taxonomy_proposals.jsonl",
    )
    aggregates = aggregate_patterns(
        patterns, prior=prior,
        auto_merge_threshold=args.auto_merge_threshold,
        borderline_threshold=args.borderline_threshold,
        min_observations=args.min_observations,
        min_repos=args.min_repos,
        min_consistency=args.min_consistency,
    )
    write_aggregates(aggregates, aggregate_path)
    clusters = [cluster for item in aggregates if (cluster := to_technique_cluster(item))]
    out_path = DATA_PROCESSED / "clusters.jsonl"
    cluster_mod.write_jsonl(clusters, out_path)
    print(
        f"Aggregated {len(patterns)} patterns into {len(aggregates)} canonical technique(s); "
        f"{len(clusters)} meet evidence thresholds; {proposal_count} parent proposal(s) await review -> {out_path}"
    )
    for c in clusters:
        print(
            f"  - {c.technique!r} (observations={c.frequency}, repos={c.distinct_repo_count}, "
            f"consistency={c.directional_consistency:.0%}, confidence={c.confidence})"
        )


def cmd_classify(args: argparse.Namespace) -> None:
    backend = args.backend or resolve_default_backend()
    clusters = cluster_mod.read_jsonl(DATA_PROCESSED / "clusters.jsonl")
    print(f"Classifying {len(clusters)} cluster(s) for generic CWV usefulness via backend={backend}...")
    classifications = classify_clusters(clusters, backend, args.model, args.timeout)
    out_path = DATA_PROCESSED / "classifications.jsonl"
    classify_mod.write_jsonl(classifications, out_path)
    n_survive = sum(1 for c in classifications if c.survives)
    print(f"Wrote {len(classifications)} classification(s) -> {out_path} ({n_survive} survive to generation)")


def cmd_antipatterns(args: argparse.Namespace) -> None:
    classifications = [Classification(**json.loads(line)) for line in
                        (DATA_PROCESSED / "classifications.jsonl").open(encoding="utf-8")]
    clusters = {c.normalized_key: c for c in cluster_mod.read_jsonl(DATA_PROCESSED / "clusters.jsonl")}
    decrease_patterns = pattern_extract.read_jsonl(DATA_PROCESSED / "perf_decrease.patterns.jsonl")

    all_matches = []
    for c in classifications:
        if not c.survives:
            continue
        cluster = clusters[c.normalized_key]
        matches = pull_antipatterns(c.normalized_key, cluster.applicable_signals, decrease_patterns)
        all_matches.extend(matches)
        print(f"  {c.technique!r} ({c.target_issue_type}): {len(matches)} anti-pattern match(es)")

    out_path = DATA_PROCESSED / "antipatterns.jsonl"
    antipatterns_mod.write_jsonl(all_matches, out_path)
    print(f"Wrote {len(all_matches)} anti-pattern match(es) -> {out_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    backend = args.backend or resolve_default_backend()
    args.candidates_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in args.candidates_dir.glob("*.md"):
        if stale_path.name != "README.md":
            stale_path.unlink()
    clusters = {c.normalized_key: c for c in cluster_mod.read_jsonl(DATA_PROCESSED / "clusters.jsonl")}
    classifications = [Classification(**json.loads(line)) for line in
                        (DATA_PROCESSED / "classifications.jsonl").open(encoding="utf-8")]
    all_antipatterns = list(antipatterns_mod.AntiPatternMatch(**json.loads(line)) for line in
                             (DATA_PROCESSED / "antipatterns.jsonl").open(encoding="utf-8")) \
        if (DATA_PROCESSED / "antipatterns.jsonl").exists() else []
    # A representative_improvements source_id can now live in either file --
    # a perf_flagged-origin PR's raw record (with the diff) only exists in
    # perf_flagged.jsonl, since it never had a bot-parsed delta to land in
    # perf_improvement.jsonl.
    flagged_source_path = DATA_PROCESSED / "perf_flagged.jsonl"
    source_records = {
        record.id: record
        for record in (
            read_pr_jsonl(DATA_PROCESSED / "perf_improvement.jsonl")
            + (read_pr_jsonl(flagged_source_path) if flagged_source_path.exists() else [])
        )
    }

    survivors = [c for c in classifications if c.survives]

    # Two+ clusters can independently classify to the SAME target_issue_type
    # (e.g. both "Fisher-Yates shuffle" and "regex hot-path" enrich
    # js-execution) -- confirmed live this silently overwrote the first
    # file with the second when generated one-at-a-time. Group and merge
    # before rendering so one candidate file gets grounded in all of them.
    by_issue_type: dict[str, list[Classification]] = {}
    for c in survivors:
        by_issue_type.setdefault(c.target_issue_type, []).append(c)

    print(f"Generating {len(by_issue_type)} platform-neutral candidate target(s) "
          f"from {len(survivors)} surviving cluster(s) via backend={backend}...")
    for issue_type, group in by_issue_type.items():
        c = group[0]
        cluster = clusters[c.normalized_key]
        if len(group) > 1:
            others = [clusters[g.normalized_key] for g in group[1:]]
            print(f"  merging {len(group)} clusters into {issue_type}.md: "
                  f"{[g.technique for g in group]}")
            cluster = cluster_mod.merge_clusters([cluster, *others])
        matches = [m for m in all_antipatterns if m.cluster_key in {g.normalized_key for g in group}]
        records = [source_records[source_id] for source_id in cluster.source_pr_ids if source_id in source_records]
        if not records:
            print(f"  skipping {issue_type}.md: no source PR records found for {cluster.source_pr_ids}")
            continue
        print(f"  rendering {issue_type}.md (technique={cluster.technique!r}, {len(matches)} anti-pattern refs)...")
        try:
            text = render_candidate(cluster, c, matches, records, backend, args.model, args.timeout)
        except Exception as exc:  # noqa: BLE001 -- one candidate's LLM failure shouldn't sink the rest of the batch
            print(f"    FAILED: {exc}")
            continue
        path = write_candidate(text, c.target_issue_type, args.candidates_dir)
        print(f"    OK -> {path} (draft + technical critic complete)")


def cmd_run_all(args: argparse.Namespace) -> None:
    cmd_source(args)
    signal_types = ("perf_improvement", "perf_decrease", "perf_flagged")
    if not any((DATA_PROCESSED / f"{t}.jsonl").exists() and (DATA_PROCESSED / f"{t}.jsonl").stat().st_size
               for t in signal_types):
        print("No perf_improvement/perf_decrease/perf_flagged records found in this window -- "
              "nothing to extract. Try a wider --hours or different --start.")
        return
    for signal_type in signal_types:
        path = DATA_PROCESSED / f"{signal_type}.jsonl"
        if path.exists() and path.stat().st_size > 0:
            args.signal_type = signal_type
            cmd_extract(args)
        else:
            pattern_extract.write_jsonl([], DATA_PROCESSED / f"{signal_type}.patterns.jsonl")
    cmd_cluster(args)
    cmd_classify(args)
    cmd_antipatterns(args)
    cmd_generate(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cwv-playbook-miner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("source", help="stage 0+1: scan GH Archive, label, fetch diffs for survivors")
    p.add_argument("--start", default=None, help="ISO datetime, e.g. 2026-08-10T13:00:00 (omit if --use-cursor and a cursor file already exists)")
    p.add_argument("--end", default=None, help="ISO datetime (default: --start + --hours)")
    p.add_argument("--hours", type=int, default=6)
    p.add_argument("--use-cursor", action="store_true", help="resume from/advance the watermark cursor file")
    p.add_argument("--append", action="store_true", help="deduplicate into existing source JSONL instead of replacing it")
    p.add_argument("--comment-only", action="store_true", help="skip retaining merge events and confirm sparse comment hits through GitHub API")
    p.add_argument("--workers", type=int, default=1, help="parallel hourly archive download/parser workers")
    p.add_argument("--api-workers", type=int, default=1, help="parallel full-comment-history workers")
    p.set_defaults(func=cmd_source)

    p = sub.add_parser("backfill", help="resumable, chunked GH Archive backfill")
    p.add_argument("--start", default=None, help="first run start; later runs may resume from the saved cursor")
    p.add_argument("--end", required=True, help="exclusive ISO end datetime")
    p.add_argument("--chunk-hours", type=int, default=24)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--api-workers", type=int, default=2)
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("import-external", help="pull real perf_improvement PRs from the external cwv-planner-dataset-v1 corpus")
    p.add_argument("--min-delta", type=float, default=15.0)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_import_external)

    p = sub.add_parser("extract", help="stage 2: LLM pattern extraction")
    p.add_argument("--signal-type", default="perf_improvement",
                    choices=["perf_improvement", "perf_decrease", "perf_flagged"])
    p.add_argument("--concurrency", type=int, default=4, help="parallel LLM batches")
    p.add_argument("--batch-size", type=int, default=8, help="compact PR records per LLM call")
    _add_llm_args(p)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("cluster", help="stage 3: canonical statistical technique aggregation")
    p.add_argument("--min-observations", type=int, default=3)
    p.add_argument("--min-repos", type=int, default=2)
    p.add_argument("--min-consistency", type=float, default=0.7)
    p.add_argument("--auto-merge-threshold", type=float, default=0.78)
    p.add_argument("--borderline-threshold", type=float, default=0.35)
    p.add_argument("--no-llm-merge", action="store_true")
    p.add_argument("--rebuild-registry", action="store_true", help="rebuild child aliases from extracted observations instead of prior registry")
    _add_llm_args(p)
    p.set_defaults(func=cmd_cluster)

    p = sub.add_parser("classify", help="stage 4: generic CWV usefulness and evidence judge")
    _add_llm_args(p)
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser("antipatterns", help="stage 5: pull matching perf_decrease anti-patterns")
    p.set_defaults(func=cmd_antipatterns)

    p = sub.add_parser("generate", help="stage 6: render candidate .md files")
    p.add_argument("--candidates-dir", type=Path, default=CANDIDATES_DIR)
    _add_llm_args(p)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("run-all", help="chain source -> extract -> cluster -> classify -> antipatterns -> generate")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--hours", type=int, default=6)
    p.add_argument("--use-cursor", action="store_true")
    p.add_argument("--candidates-dir", type=Path, default=CANDIDATES_DIR)
    p.add_argument("--concurrency", type=int, default=4, help="parallel LLM batches")
    p.add_argument("--batch-size", type=int, default=8, help="compact PR records per LLM call")
    p.add_argument("--min-observations", type=int, default=3)
    p.add_argument("--min-repos", type=int, default=2)
    p.add_argument("--min-consistency", type=float, default=0.7)
    p.add_argument("--auto-merge-threshold", type=float, default=0.78)
    p.add_argument("--borderline-threshold", type=float, default=0.35)
    p.add_argument("--no-llm-merge", action="store_true")
    p.add_argument("--rebuild-registry", action="store_true", help="rebuild child aliases from extracted observations instead of prior registry")
    _add_llm_args(p)
    p.set_defaults(func=cmd_run_all)

    return parser


def main() -> None:
    # Load .env once, centrally, before any subcommand runs -- llm/client.py
    # also lazily loads it on first LLM call, but import-external needs
    # HF_TOKEN before ever touching the LLM client, so it can't rely on that.
    from cwv_playbook_miner.llm.client import _ensure_env_loaded
    _ensure_env_loaded()

    parser = build_parser()
    args = parser.parse_args()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
