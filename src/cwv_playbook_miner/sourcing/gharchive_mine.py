"""Stage 0: scan GH Archive for candidate CWV-relevant merged PRs, using only
free signal from the raw event stream (verified live in this environment --
see docs/pipeline-design.md for the numbers).

Four free filters, applied across the whole scanned date range and then
intersected with a merge event:
  1. IssueCommentEvent from a `[bot]` actor, on a PR, whose body matches a
     narrow structured-report marker set (BOT_COMMENT_MARKERS) -- a cheap
     pre-filter -- NOT sufficient alone, see the false-positive-rate finding
     in docs/pipeline-design.md; fine-grained per-tool fingerprinting
     happens in labeling/registry.py, stage 1.
  2. PullRequestReviewEvent / PullRequestReviewCommentEvent from a `[bot]`
     actor matching the same narrow marker set -- some CI perf bots post
     their report via the Review API instead of a plain issue comment; same
     downstream Tier-A template-matching path as (1), just a second place to
     find it. Confirmed live: GH Archive strips PR title/body from
     PullRequestEvent entirely, but these two event types still carry
     payload.pull_request.number, so they identify a PR exactly like a
     comment hit does.
  3. PullRequestReviewEvent / PullRequestReviewCommentEvent from a non-bot
     actor matching a broader, human-language marker set (HUMAN_PERF_MARKERS)
     -- real reviewers writing about performance in plain prose. These never
     match a structured bot-report template (registry.py's generic_fallback
     always returns tier B / no parsed delta), so they're NOT run through
     the label_pr/match_template path at all; they're a separate discovery
     signal handled by human_flagged_candidates() and given to the LLM
     extraction stage to judge relevance and direction directly (see
     cli.py's cmd_source "flagged" branch and
     extraction/pattern_extract.py's inferred_signal_type field).
  4. PullRequestEvent with payload.action == "merged" (a direct action value
     in the real event schema, confirmed live -- no nested `.merged` check
     needed).

Only PRs that clear a comment/review filter AND the merge filter ever need a
`gh api` call, and only for the one thing neither the archive nor GraphQL
gives for free: diff/patch text.

Known limitation, stated plainly rather than silently handled: comment and
merge signal for the same PR can land in different scan windows (a bot
comment today, the PR merges next week). This implementation intersects
within a single `mine` invocation's date range only -- carrying "orphan"
signal forward across separate runs is not implemented yet. Widen the range
per run if this matters for a given demo/backfill.
"""

from __future__ import annotations

import json
import multiprocessing
import re
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

# Broader, human-language marker set for real reviewers/review comments --
# deliberately looser than BOT_COMMENT_MARKERS since it's matched against
# prose, not a structured bot report. Only applied to non-bot actors (see
# _scan_hour), so it doesn't widen/duplicate the existing bot-template path.
# A real regex (not substring-`in`, unlike comment_matches_markers) since
# the short acronyms (LCP/CLS/INP/...) need word boundaries to avoid
# matching inside unrelated words.
HUMAN_PERF_MARKERS = re.compile(
    r"\b(lighthouse|web[- ]?vitals?|core web vitals?|LCP|CLS|INP|TBT|TTI|FCP|TTFB|"
    r"bundle[- ]?size|code[- ]?split|lazy[- ]?load|tree[- ]?shak\w*|performance budget|"
    r"reduce (bundle|payload|render|paint)|speed up|optimi[sz]e (render|load|paint|hydration)|"
    r"defer (script|render|load)|hydration cost|render blocking|critical (css|path)|"
    r"first contentful paint|largest contentful paint|cumulative layout shift|"
    r"interaction to next paint|time to interactive)\b",
    re.IGNORECASE,
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


# Automated PR-review tools that don't follow the `[bot]`-suffix convention
# GitHub uses for App-backed actors. Confirmed live: GitHub's own Copilot PR
# reviewer posts as plain login "Copilot" (display_login
# "copilot-pull-request-reviewer"), no [bot] suffix -- its auto-generated
# "## Pull request overview" summaries were leaking into the human-signal
# channel undetected. Known-incomplete by nature (new tools can pick any
# name); the length guard in human_comment_matches_markers is the general
# backstop for whatever this list misses.
KNOWN_BOT_LOGINS = {"copilot"}

# Real human review comments are short. Automated review-tool dumps
# (CodeRabbit, verification-agent-style bots, etc.) are typically thousands
# of characters of collapsible <details> sections covering many unrelated
# findings -- long enough that a broad marker regex matches somewhere by
# chance even on an unrelated PR. Confirmed live: this is what let CodeRabbit
# noise through even when comment_matches_markers correctly gated it out of
# the bot-template path (see human_flagged_candidates for the actor-side fix).
HUMAN_SIGNAL_MAX_BODY_LEN = 1500


def is_bot_actor(login: str) -> bool:
    login = login or ""
    return login.endswith("[bot]") or login.lower() in KNOWN_BOT_LOGINS


def comment_matches_markers(body: str) -> bool:
    b = (body or "").lower()
    return any(m in b for m in BOT_COMMENT_MARKERS)


def human_comment_matches_markers(body: str) -> bool:
    body = body or ""
    if len(body) > HUMAN_SIGNAL_MAX_BODY_LEN:
        return False
    return bool(HUMAN_PERF_MARKERS.search(body))


@dataclass
class CommentHit:
    repo: str
    pr_number: int
    actor: str
    body: str
    created_at: str
    # "bot_comment" (IssueCommentEvent, the original channel), "review" /
    # "review_comment" (PullRequestReviewEvent / PullRequestReviewCommentEvent,
    # bot or human depending on which marker set matched -- see _scan_hour).
    source: str = "bot_comment"


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


def _hit_from_review_event(repo: str, actor: str, number: int, body: str, source: str, created_at: str) -> CommentHit | None:
    """Shared classification for PullRequestReviewEvent / PullRequestReviewCommentEvent:
    bot actor + narrow template markers -> same Tier-A path as a bot comment;
    non-bot actor + broad human-language markers -> a separate, unquantified
    discovery signal (see human_flagged_candidates / cli.py's "flagged" branch)."""
    if is_bot_actor(actor):
        if not comment_matches_markers(body):
            return None
    elif not human_comment_matches_markers(body):
        return None
    return CommentHit(repo=repo, pr_number=number, actor=actor, body=body, created_at=created_at, source=source)


# Module-level (not a closure) so it's picklable for ProcessPoolExecutor.
# `fetch_hour_events` is referenced by module attribute lookup at call time
# (not captured), so a test that monkeypatches
# `gharchive_mine.fetch_hour_events` before scan_range creates its pool is
# still honored by forked workers (fork copies the already-patched module
# state; default start method on Linux) -- confirmed live.
def _scan_hour(dt: datetime, event_types: frozenset[str]):
    hits: list[CommentHit] = []
    merges: dict[tuple[str, int], dict] = {}
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

        elif etype == "PullRequestReviewCommentEvent":
            payload = e.get("payload", {})
            actor = e.get("actor", {}).get("login", "")
            number = (payload.get("pull_request") or {}).get("number")
            body = (payload.get("comment") or {}).get("body") or ""
            if number is None:
                continue
            hit = _hit_from_review_event(repo, actor, number, body, "review_comment", e.get("created_at", ""))
            if hit is not None:
                hits.append(hit)

        elif etype == "PullRequestReviewEvent":
            payload = e.get("payload", {})
            actor = e.get("actor", {}).get("login", "")
            number = (payload.get("pull_request") or {}).get("number")
            body = (payload.get("review") or {}).get("body") or ""
            if number is None:
                continue
            hit = _hit_from_review_event(repo, actor, number, body, "review", e.get("created_at", ""))
            if hit is not None:
                hits.append(hit)

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


def human_flagged_candidates(comment_hits: list[CommentHit]) -> set[tuple[str, int]]:
    """Distinct (repo, pr_number) pairs flagged by a non-bot review or inline
    review comment matching HUMAN_PERF_MARKERS. No template parsing here --
    this is pure discovery; the LLM extraction stage judges relevance and
    infers direction directly from the diff + this comment's text (see
    cli.py's cmd_source "flagged" branch).

    The `source in ("review", "review_comment")` check alone is NOT enough:
    a bot actor's hit can also carry that source (it just means the event
    type, not who/how it matched -- see _hit_from_review_event). Confirmed
    live: a `[bot]`-suffixed automated review tool's multi-thousand-character
    dump can coincidentally contain a narrow BOT_COMMENT_MARKERS substring
    (e.g. "bundle size" mentioned in passing while reviewing unrelated code),
    which is a valid bot-template-path hit but must NOT also count as a
    human-flagged discovery signal. is_bot_actor is the actual gate."""
    return {
        (h.repo, h.pr_number) for h in comment_hits
        if h.source in ("review", "review_comment") and not is_bot_actor(h.actor)
    }


def scan_range(
    start: datetime, end: datetime, cursor_path: Path | None = None, on_progress=None,
    track_merges: bool = True, workers: int = 1,
) -> ScanResult:
    base_types = {"IssueCommentEvent", "PullRequestReviewEvent", "PullRequestReviewCommentEvent"}
    event_types = frozenset(base_types | {"PullRequestEvent"} if track_merges else base_types)

    result = ScanResult()
    hours = list(iter_hours(start, end))
    if workers <= 1:
        completed = (_scan_hour(dt, event_types) for dt in hours)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        # CPU-bound (gzip decompress + json.loads), so ThreadPoolExecutor
        # gave zero speedup under the GIL -- measured live, 4 vs 32 threads
        # both ~1.2 hours/sec. `fork` context (Linux default) is forced
        # explicitly rather than left implicit: it's both faster than
        # `spawn` (no fresh re-import per worker) and what makes
        # pre-pool-creation monkeypatching of fetch_hour_events still work
        # in tests.
        pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork"))
        futures = [pool.submit(_scan_hour, dt, event_types) for dt in hours]
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
