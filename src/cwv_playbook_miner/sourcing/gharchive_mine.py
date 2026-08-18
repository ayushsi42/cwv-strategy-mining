"""Stage 0: scan GH Archive for candidate CWV-relevant merged PRs, using only
free signal from the raw event stream (verified live in this environment --
see docs/pipeline-design.md for the numbers).

Two free filters, applied across the whole scanned date range and then
intersected:
  1. IssueCommentEvent from a `[bot]` actor, on a PR, whose body matches a
     broad marker set (a cheap pre-filter -- NOT sufficient alone, see the
     false-positive-rate finding in docs/pipeline-design.md; fine-grained
     per-tool fingerprinting happens in labeling/registry.py, stage 1).
  2. PullRequestEvent with payload.action == "merged" (a direct action value
     in the real event schema, confirmed live -- no nested `.merged` check
     needed).

Only PRs that clear both ever need a `gh api` call, and only for the one
thing neither the archive nor GraphQL gives for free: diff/patch text.

Known limitation, stated plainly rather than silently handled: comment and
merge signal for the same PR can land in different scan windows (a bot
comment today, the PR merges next week). This implementation intersects
within a single `mine` invocation's date range only -- carrying "orphan"
signal forward across separate runs is not implemented yet. Widen the range
per run if this matters for a given demo/backfill.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from cwv_playbook_miner.sourcing.gharchive_fetch import fetch_hour_events, iter_hours

BOT_COMMENT_MARKERS = (
    "lighthouse", "core web vitals", "[bundle]", "web vitals",
    "performance budget", "pagespeed", "webpagetest", "calibre",
    "unlighthouse", "bundlesize", "bundle size", "relative-ci",
)
TRIVIAL_PATH_PREFIXES = (".github/", "docs/", "README", ".circleci/", ".gitlab-ci")
FRONTEND_EXTENSIONS = (
    # Code
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro",
    ".css", ".scss", ".less", ".html",
    # Images/fonts -- confirmed live this was a real gap: a genuine
    # perf_improvement PR (apikujuni-source/the-gleaning-ground#32, +25
    # points) only touched a .mjs file and was wrongly excluded before .mjs
    # was added above. A PR that's PURELY an image-format/font swap (no .js/
    # .css touched at all) would have been silently excluded entirely --
    # exactly the shape of two of the 19 existing playbook issue types
    # (image-sizing, font-format).
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg",
    ".woff", ".woff2", ".ttf", ".otf",
)


def is_bot_actor(login: str) -> bool:
    return (login or "").endswith("[bot]")


def comment_matches_markers(body: str) -> bool:
    b = (body or "").lower()
    return any(m in b for m in BOT_COMMENT_MARKERS)


@dataclass
class CommentHit:
    repo: str
    pr_number: int
    actor: str
    body: str
    created_at: str


@dataclass
class ScanResult:
    comment_hits: list[CommentHit] = field(default_factory=list)
    merged_prs: dict[tuple[str, int], dict] = field(default_factory=dict)  # (repo, pr) -> {merged_at, head_sha}
    hours_scanned: int = 0
    hours_skipped: int = 0

    @property
    def free_candidates(self) -> list[tuple[str, int]]:
        """PRs where BOTH free filters confirm within the scanned window --
        zero `gh api` spend needed for merge confirmation."""
        seen = {(h.repo, h.pr_number) for h in self.comment_hits}
        return sorted(seen & self.merged_prs.keys())

    @property
    def unconfirmed_comment_prs(self) -> list[tuple[str, int]]:
        """Comment-hit PRs with no free merge event in this window -- the
        common case (bot comment and merge often land in different
        windows). Worth a cheap, bounded `gh api` merge check per PR (see
        check_pr_merged) since comment-hit volume is sparse by construction."""
        seen = {(h.repo, h.pr_number) for h in self.comment_hits}
        return sorted(seen - self.merged_prs.keys())


def scan_range(
    start: datetime, end: datetime, cursor_path: Path | None = None, on_progress=None,
    track_merges: bool = True, workers: int = 1,
) -> ScanResult:
    def scan_hour(dt):
        hits = []
        merges = {}
        event_types = {"IssueCommentEvent", "PullRequestEvent"} if track_merges else {"IssueCommentEvent"}
        events = fetch_hour_events(dt, type_filter=event_types)
        if events is None:
            return dt, None, None
        for e in events:
            etype = e.get("type")
            repo = e.get("repo", {}).get("name")
            if not repo:
                continue

            if etype == "IssueCommentEvent":
                actor = e.get("actor", {}).get("login", "")
                if not is_bot_actor(actor):
                    continue
                payload = e.get("payload", {})
                issue = payload.get("issue") or {}
                if "pull_request" not in issue:
                    continue
                comment = payload.get("comment") or {}
                body = comment.get("body") or ""
                if not comment_matches_markers(body):
                    continue
                number = issue.get("number")
                if number is None:
                    continue
                hits.append(
                    CommentHit(repo=repo, pr_number=number, actor=actor,
                               body=body, created_at=e.get("created_at", ""))
                )

            elif etype == "PullRequestEvent":
                payload = e.get("payload", {})
                if payload.get("action") != "merged":
                    continue
                number = payload.get("number")
                pr = payload.get("pull_request") or {}
                if number is None:
                    continue
                merges[(repo, number)] = {
                    "merged_at": e.get("created_at", ""),
                    "head_sha": (pr.get("head") or {}).get("sha"),
                }

        return dt, hits, merges

    result = ScanResult()
    hours = list(iter_hours(start, end))
    if workers <= 1:
        completed = (scan_hour(dt) for dt in hours)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        pool = ThreadPoolExecutor(max_workers=workers)
        futures = [pool.submit(scan_hour, dt) for dt in hours]
        completed = (future.result() for future in as_completed(futures))

    try:
        for dt, hits, merges in completed:
            if hits is None:
                result.hours_skipped += 1
            else:
                result.hours_scanned += 1
                result.comment_hits.extend(hits)
                result.merged_prs.update(merges)
            if on_progress:
                on_progress(dt, result)
    finally:
        if workers > 1:
            pool.shutdown(wait=True, cancel_futures=True)

    if cursor_path is not None and hours:
        from cwv_playbook_miner.sourcing.gharchive_fetch import write_cursor
        write_cursor(cursor_path, hours[-1])

    return result


# --- gh api, subprocess-based. `gh auth token` piped into a raw `requests`
# call 401s in this environment -- `gh api ...` itself works. Verified live
# in the smol-planner reference code's own docstring; not re-derived here. ---

def gh_api(path: str, timeout: int = 30) -> dict | list | None:
    try:
        proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        error = proc.stderr.lower()
        if "rate limit" in error or "secondary rate" in error:
            raise RuntimeError(
                "GitHub API rate limit reached; stopping before the current "
                "backfill chunk is checkpointed so it can be resumed safely"
            )
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def fetch_pr_comments(repo: str, pr_number: int) -> list[CommentHit]:
    """Getting a real before/after delta needs 2+ bot comments on the SAME
    PR, which in practice usually spans that PR's whole review lifecycle
    (days of pushes/re-runs) -- confirmed live: PRs with exactly one
    Tier-A comment in a 9-hour scan window stayed `unlabeled` for lack of a
    second data point. Rather than requiring a scan window lucky enough to
    catch both, this does one targeted `gh api` call (bounded to PRs
    already flagged promising by the free scan) to pull the PR's full
    comment history and resolve the delta immediately."""
    comments = gh_api(f"repos/{repo}/issues/{pr_number}/comments")
    if not comments:
        return []
    return [
        CommentHit(
            repo=repo, pr_number=pr_number,
            actor=(c.get("user") or {}).get("login", ""),
            body=c.get("body") or "", created_at=c.get("created_at", ""),
        )
        for c in comments
    ]


def check_pr_merged(repo: str, pr_number: int) -> bool:
    """Fallback merge check for the (common, documented) case where a
    comment hit's free merge event landed outside the scanned window. Only
    called for the small set of comment-hit PRs that don't already have a
    free merge event, so the `gh api` spend stays proportional to real
    candidates, not scan volume -- confirmed cheap in practice (a handful
    of calls even for a multi-hour scan, since bot-comment hits are sparse)."""
    pr = gh_api(f"repos/{repo}/pulls/{pr_number}")
    return bool(pr and pr.get("merged"))


def fetch_pr_diff(repo: str, pr_number: int) -> list[dict] | None:
    """The one non-free call in stage 0: fetches changed files + patch text
    for a PR that already cleared both free filters."""
    files = gh_api(f"repos/{repo}/pulls/{pr_number}/files")
    if files is None:
        return None
    return [{"filename": f["filename"], "patch": f.get("patch", "")} for f in files]


def is_ci_docs_only(changed_files: list[dict]) -> bool:
    return all(f["filename"].startswith(TRIVIAL_PATH_PREFIXES) for f in changed_files)


def touches_frontend(changed_files: list[dict]) -> bool:
    return any(f["filename"].lower().endswith(FRONTEND_EXTENSIONS) for f in changed_files)
