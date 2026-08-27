"""CLI entrypoint for cwv-playbook-miner.

Two command groups:

  Sourcing (GH Archive → raw PR records):
    source      — live scan a time window
    backfill    — resumable chunked multi-day scan

  AEM playbook pipeline (raw records → AEM-format playbooks):
    triage           — stage 1: summarise + embed + route
    semantic-cluster — stage 2b: HDBSCAN novel clustering
    enrich-extract   — stage 2a: evidence selection for existing playbooks
    generate-playbooks — stage 3: AEM-format generation (two-pass)
    playbooks        — full chain: all four stages above
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord, read_jsonl as read_pr_jsonl, write_jsonl as write_pr_jsonl
from cwv_playbook_miner.labeling.signal_label import label_scan_result
from cwv_playbook_miner.llm.client import resolve_default_backend
from cwv_playbook_miner.sourcing.gharchive_fetch import read_cursor, write_cursor
from cwv_playbook_miner.sourcing.gharchive_mine import (
    check_pr_merged, fetch_pr_comments, fetch_pr_diff,
    human_flagged_candidates, is_ci_docs_only, scan_range, touches_frontend,
)

DATA_RAW = Path("data/raw")
DATA_PROCESSED = Path("data/processed")
CURSOR_PATH = DATA_RAW / "gharchive_cursor.json"
HANDOFF_DIR = Path("cwv-playbooks-handoff")
PLAYBOOKS_DIR = Path("playbooks")
CACHE_DIR = DATA_PROCESSED / ".triage_cache"


def _add_llm_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend", default=None,
                   help="openai | openai-compatible (default: openai, requires OPENAI_API_KEY)")
    p.add_argument("--model", default=None)
    p.add_argument("--timeout", type=int, default=120)


def _add_embed_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--embed-provider", default="openai",
                   help="openai | openai-compatible | sentence-transformers")
    p.add_argument("--embed-model", default=None, help="override default embedding model")
    p.add_argument("--embed-base-url", default=None,
                   help="base URL for openai-compatible embedding endpoint")


# ---------------------------------------------------------------------------
# Sourcing commands
# ---------------------------------------------------------------------------

def _resolve_start(args: argparse.Namespace) -> datetime:
    if args.start:
        return datetime.fromisoformat(args.start)
    if not args.use_cursor:
        raise SystemExit("--start is required unless --use-cursor is set")
    cursor = read_cursor(CURSOR_PATH)
    if cursor is None:
        raise SystemExit(f"--use-cursor set but no cursor file at {CURSOR_PATH} — pass --start")
    return cursor + timedelta(hours=1)


def cmd_source(args: argparse.Namespace) -> None:
    start = _resolve_start(args)
    end = datetime.fromisoformat(args.end) if args.end else start + timedelta(hours=args.hours)

    print(f"Scanning GH Archive {start.isoformat()} -> {end.isoformat()} "
          f"({int((end - start).total_seconds() // 3600)} hours)...")

    def progress(dt, result):
        if result.hours_scanned % 5 == 0:
            print(f"  ...{result.hours_scanned} hours scanned, "
                  f"{len(result.comment_hits)} comment hits, "
                  f"{len(result.merged_prs)} merges seen so far")

    result = scan_range(
        start, end, on_progress=progress,
        track_merges=not getattr(args, "comment_only", False),
        workers=getattr(args, "workers", 1),
    )
    print(f"Scan done: {result.hours_scanned} hours scanned "
          f"({result.hours_skipped} skipped/unpublished), "
          f"{len(result.comment_hits)} bot-comment hits, "
          f"{len(result.merged_prs)} merged PRs seen, "
          f"{len(result.free_candidates)} candidates clear both free filters.")

    labeled = label_scan_result(result.comment_hits)
    labeled_by_pr = {(pr.repo, pr.pr_number): pr for pr in labeled}
    tier_a = [pr for pr in labeled if pr.tier == "A"]
    print(f"  structural fingerprinting: {len(labeled)} broad PR hit(s) -> {len(tier_a)} Tier-A PR(s)")

    unresolved = [lp for lp in tier_a if lp.signal_type == "unlabeled"]

    def resolve_full_history(lp):
        full_comments = fetch_pr_comments(lp.repo, lp.pr_number)
        if len(full_comments) <= lp.n_comments_seen:
            return lp
        from cwv_playbook_miner.labeling.signal_label import label_pr
        return label_pr(lp.repo, lp.pr_number, full_comments)

    if unresolved:
        print(f"  resolving full comment history for {len(unresolved)} Tier-A PR(s) "
              f"with {getattr(args, 'api_workers', 1)} worker(s)...")
        with ThreadPoolExecutor(max_workers=getattr(args, "api_workers", 1)) as pool:
            futures = {pool.submit(resolve_full_history, lp): lp for lp in unresolved}
            for future in as_completed(futures):
                original = futures[future]
                relabeled = future.result()
                labeled_by_pr[(original.repo, original.pr_number)] = relabeled
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
    print(f"  {len(measurable)} measurable PR(s), {len(candidates)} confirmed merged "
          f"({len(fallback_confirmed)} via fallback check)")

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
            id=f"{repo}#{pr_number}", repo=repo, pr_number=pr_number,
            signal_type=lp.signal_type, metric_key=lp.metric_key,
            before=lp.before, after=lp.after, delta=lp.delta,
            changed_files=changed_files, template_names=lp.template_names,
            merged_at=merged_at_by_pr.get((repo, pr_number)),
        )
        (perf_improvement if lp.signal_type == "perf_improvement" else perf_decrease).append(record)

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
        print(f"  {len(flagged)} human-flagged PR(s) (non-bot review/review-comment), "
              f"{len(flagged_merged)} confirmed merged")

    hit_by_flagged_pr = {
        (h.repo, h.pr_number): h for h in result.comment_hits
        if h.source in ("review", "review_comment")
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
            id=f"{repo}#{pr_number}", repo=repo, pr_number=pr_number,
            signal_type="perf_flagged", metric_key=None, before=None, after=None, delta=None,
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
            by_id = {r.id: r for r in existing}
            by_id.update({r.id: r for r in records})
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
    """Resumable chunked GH Archive sweep."""
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
            start=current.isoformat(), end=chunk_end.isoformat(),
            hours=args.chunk_hours, use_cursor=False, append=True,
            comment_only=True, workers=args.workers, api_workers=args.api_workers,
        )
        cmd_source(chunk_args)
        write_cursor(CURSOR_PATH, chunk_end - timedelta(hours=1))
        print(f"Checkpointed completed hour {chunk_end - timedelta(hours=1)}")
        current = chunk_end
    print(f"Backfill complete through {end.isoformat()}")


# ---------------------------------------------------------------------------
# AEM playbook pipeline commands
# ---------------------------------------------------------------------------

def cmd_triage(args: argparse.Namespace) -> None:
    """Stage 1: summarise records, embed, route against existing playbooks."""
    from cwv_playbook_miner.triage.triage import run_triage, write_triage_jsonl

    backend = args.backend or resolve_default_backend()
    handoff_dir = Path(args.handoff_dir)
    if not handoff_dir.exists():
        raise SystemExit(f"Handoff dir not found: {handoff_dir}. Pass --handoff-dir.")

    records = run_triage(
        [DATA_PROCESSED / f for f in ("perf_improvement.jsonl", "perf_decrease.jsonl", "perf_flagged.jsonl")],
        handoff_dir,
        backend=backend,
        model=args.model,
        embed_provider=args.embed_provider,
        embed_model=args.embed_model,
        embed_base_url=args.embed_base_url,
        summarize_workers=args.workers,
        timeout=args.timeout,
        cache_dir=CACHE_DIR if not args.no_cache else None,
        high_threshold=args.high_threshold,
        low_threshold=args.low_threshold,
    )

    out = DATA_PROCESSED / "triage.jsonl"
    write_triage_jsonl(records, out)
    by_route: dict[str, int] = {}
    for r in records:
        by_route[r.route] = by_route.get(r.route, 0) + 1
    print(f"Wrote {len(records)} triage records → {out}")
    print(f"  existing: {by_route.get('existing', 0)}, "
          f"novel: {by_route.get('novel', 0)}, "
          f"drop: {by_route.get('drop', 0)}")


def cmd_semantic_cluster(args: argparse.Namespace) -> None:
    """Stage 2b: HDBSCAN clustering of novel pool → labelled NovelClusters."""
    from cwv_playbook_miner.triage.triage import read_triage_jsonl
    from cwv_playbook_miner.extraction.semantic_cluster import cluster_novel_records, write_jsonl

    triage_path = DATA_PROCESSED / "triage.jsonl"
    if not triage_path.exists():
        raise SystemExit(f"Run `triage` first — {triage_path} not found.")

    triage_records = read_triage_jsonl(triage_path)
    pr_by_id: dict[str, PRRecord] = {}
    for path in (DATA_PROCESSED / f for f in
                 ("perf_improvement.jsonl", "perf_decrease.jsonl", "perf_flagged.jsonl")):
        if path.exists():
            for pr in read_pr_jsonl(path):
                pr_by_id[pr.id] = pr

    backend = args.backend or resolve_default_backend()
    clusters = cluster_novel_records(
        triage_records, pr_by_id,
        embed_provider=args.embed_provider,
        embed_model=args.embed_model,
        embed_base_url=args.embed_base_url,
        backend=backend, model=args.model, timeout=args.timeout,
        min_cluster_size=args.min_cluster_size,
    )

    out = DATA_PROCESSED / "novel_clusters.jsonl"
    write_jsonl(clusters, out)
    print(f"Wrote {len(clusters)} novel clusters → {out}")
    for c in clusters:
        print(f"  [{c.issue_type}] {len(c.source_pr_ids)} PRs, "
              f"{c.distinct_repo_count} repos, "
              f"{c.directional_consistency:.0%} consistent, "
              f"flavors={c.applicable_flavors}")


def cmd_enrich_extract(args: argparse.Namespace) -> None:
    """Stage 2a: select enrichment evidence per existing playbook."""
    from cwv_playbook_miner.triage.triage import read_triage_jsonl
    from cwv_playbook_miner.extraction.enrich_extract import extract_enrichments, write_jsonl

    triage_path = DATA_PROCESSED / "triage.jsonl"
    if not triage_path.exists():
        raise SystemExit(f"Run `triage` first — {triage_path} not found.")

    triage_records = read_triage_jsonl(triage_path)
    pr_by_id: dict[str, PRRecord] = {}
    for path in (DATA_PROCESSED / f for f in
                 ("perf_improvement.jsonl", "perf_decrease.jsonl", "perf_flagged.jsonl")):
        if path.exists():
            for pr in read_pr_jsonl(path):
                pr_by_id[pr.id] = pr

    evidence = extract_enrichments(triage_records, pr_by_id)
    out = DATA_PROCESSED / "enrichments.jsonl"
    write_jsonl(evidence, out)
    print(f"Wrote {len(evidence)} enrichment evidence records → {out}")


def cmd_generate_playbooks(args: argparse.Namespace) -> None:
    """Stage 3: generate new playbook files and enrichment blocks."""
    from cwv_playbook_miner.extraction.semantic_cluster import read_jsonl as read_clusters
    from cwv_playbook_miner.extraction.enrich_extract import read_jsonl as read_enrichments
    from cwv_playbook_miner.generation.render_playbook import (
        render_new_playbook, render_enrichment, write_playbook, write_enrichment,
    )

    backend = args.backend or resolve_default_backend()
    handoff_dir = Path(args.handoff_dir)
    if not handoff_dir.exists():
        raise SystemExit(f"Handoff dir not found: {handoff_dir}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pr_by_id: dict[str, PRRecord] = {}
    for path in (DATA_PROCESSED / f for f in
                 ("perf_improvement.jsonl", "perf_decrease.jsonl", "perf_flagged.jsonl")):
        if path.exists():
            for pr in read_pr_jsonl(path):
                pr_by_id[pr.id] = pr

    clusters_path = DATA_PROCESSED / "novel_clusters.jsonl"
    if clusters_path.exists():
        clusters = read_clusters(clusters_path)
        print(f"Generating {len(clusters)} new playbooks...")
        for cluster in clusters:
            source_prs = [pr_by_id[pid] for pid in cluster.source_pr_ids if pid in pr_by_id]
            print(f"  [{cluster.issue_type}] {len(source_prs)} source PRs")
            text = render_new_playbook(
                cluster, source_prs, handoff_dir,
                backend=backend, model=args.model, timeout=args.timeout,
            )
            path = write_playbook(text, cluster.issue_type, output_dir)
            print(f"    → {path}")

    if not args.new_only:
        enrichments_path = DATA_PROCESSED / "enrichments.jsonl"
        if enrichments_path.exists():
            enrichments = read_enrichments(enrichments_path)
            print(f"Generating {len(enrichments)} enrichment blocks...")
            for ev in enrichments:
                approach_prs = [pr_by_id[pid] for pid in ev.approach_pr_ids if pid in pr_by_id]
                antipattern_prs = [pr_by_id[pid] for pid in ev.antipattern_pr_ids if pid in pr_by_id]
                if not approach_prs and not antipattern_prs:
                    continue
                print(f"  [{ev.playbook_id}] {len(approach_prs)} approach + "
                      f"{len(antipattern_prs)} anti-pattern PRs")
                text = render_enrichment(
                    ev, approach_prs, antipattern_prs, handoff_dir,
                    backend=backend, model=args.model, timeout=args.timeout,
                )
                path = write_enrichment(text, ev.playbook_id, output_dir)
                print(f"    → {path}")

    print(f"Done. Output in {output_dir}/")


def cmd_playbooks(args: argparse.Namespace) -> None:
    """Full chain: triage → semantic-cluster + enrich-extract → generate-playbooks."""
    args.no_cache = False
    cmd_triage(args)
    cmd_semantic_cluster(args)
    cmd_enrich_extract(args)
    cmd_generate_playbooks(args)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cwv-playbook-miner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("source", help="scan GH Archive window, label, fetch diffs for survivors")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--hours", type=int, default=6)
    p.add_argument("--use-cursor", action="store_true")
    p.add_argument("--append", action="store_true")
    p.add_argument("--comment-only", action="store_true")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--api-workers", type=int, default=1)
    p.set_defaults(func=cmd_source)

    p = sub.add_parser("backfill", help="resumable chunked GH Archive backfill")
    p.add_argument("--start", default=None)
    p.add_argument("--end", required=True)
    p.add_argument("--chunk-hours", type=int, default=24)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--api-workers", type=int, default=2)
    p.set_defaults(func=cmd_backfill)

    _HANDOFF = "path to cwv-playbooks-handoff dir (default: cwv-playbooks-handoff)"
    _OUTPUT = "output dir for generated playbooks (default: playbooks/)"

    p = sub.add_parser("triage", help="[AEM] stage 1: summarise + embed + route")
    p.add_argument("--handoff-dir", default=str(HANDOFF_DIR), help=_HANDOFF)
    p.add_argument("--high-threshold", type=float, default=0.78)
    p.add_argument("--low-threshold", type=float, default=0.45)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--no-cache", action="store_true")
    _add_llm_args(p)
    _add_embed_args(p)
    p.set_defaults(func=cmd_triage)

    p = sub.add_parser("semantic-cluster", help="[AEM] stage 2b: HDBSCAN novel clustering")
    p.add_argument("--min-cluster-size", type=int, default=4)
    _add_llm_args(p)
    _add_embed_args(p)
    p.set_defaults(func=cmd_semantic_cluster)

    p = sub.add_parser("enrich-extract", help="[AEM] stage 2a: evidence selection for existing playbooks")
    p.set_defaults(func=cmd_enrich_extract)

    p = sub.add_parser("generate-playbooks", help="[AEM] stage 3: two-pass AEM-format generation")
    p.add_argument("--handoff-dir", default=str(HANDOFF_DIR), help=_HANDOFF)
    p.add_argument("--output-dir", default=str(PLAYBOOKS_DIR), help=_OUTPUT)
    p.add_argument("--new-only", action="store_true")
    _add_llm_args(p)
    p.set_defaults(func=cmd_generate_playbooks)

    p = sub.add_parser("playbooks", help="[AEM] full chain: triage → cluster/enrich → generate")
    p.add_argument("--handoff-dir", default=str(HANDOFF_DIR), help=_HANDOFF)
    p.add_argument("--output-dir", default=str(PLAYBOOKS_DIR), help=_OUTPUT)
    p.add_argument("--high-threshold", type=float, default=0.78)
    p.add_argument("--low-threshold", type=float, default=0.45)
    p.add_argument("--min-cluster-size", type=int, default=4)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--new-only", action="store_true")
    _add_llm_args(p)
    _add_embed_args(p)
    p.set_defaults(func=cmd_playbooks)

    return parser


def main() -> None:
    from cwv_playbook_miner.llm.client import _ensure_env_loaded
    _ensure_env_loaded()
    parser = build_parser()
    args = parser.parse_args()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
