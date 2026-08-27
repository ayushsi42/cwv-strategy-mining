"""Backfills title/body/comments/reviews for PRRecords via GitHub's GraphQL
API, batched via query aliases.

Why GraphQL over REST: getting this for all 14,965 PRs needs up to 4 REST
calls each (PR object, issue comments, review comments, reviews) -- ~60,000
requests against a 5,000/hr limit. GraphQL batches ~40 PRs into one request
for ~13 points, comfortably inside the 5,000-point/hr GraphQL budget.

Batch size chosen empirically, live against the real API: 100 PRs/query
started hitting GitHub's per-query RESOURCE_LIMITS_EXCEEDED partway through
(aliases from ~55 onward came back null); 25/40/50 all came back clean. Any
batch that still trips the limit (a PR with unusually large comment/review
counts) is retried automatically in a halved sub-batch, recursing down to
single-PR queries if needed.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord

BATCH_SIZE = 40
COMMENTS_PAGE = 50
REVIEWS_PAGE = 30
REVIEW_COMMENTS_PAGE = 30
MAX_RETRY_DEPTH = 6

_FRAGMENT = f"""
fragment prFields on PullRequest {{
  title
  body
  comments(first: {COMMENTS_PAGE}) {{ totalCount nodes {{ body createdAt author {{ login }} }} }}
  reviews(first: {REVIEWS_PAGE}) {{
    totalCount
    nodes {{
      body state createdAt author {{ login }}
      comments(first: {REVIEW_COMMENTS_PAGE}) {{ totalCount nodes {{ body path createdAt author {{ login }} }} }}
    }}
  }}
}}
"""


@dataclass
class EnrichResult:
    record_id: str
    found: bool
    title: str | None = None
    body: str | None = None
    comments: list[dict] | None = None
    truncated: bool = False


def _gh_graphql(query: str, timeout: int = 60, retries: int = 4) -> dict:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            proc = subprocess.run(
                ["gh", "api", "graphql", "-f", f"query={query}"],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            last_err = exc
            time.sleep(2 ** attempt)
            continue
        # `gh` exits 1 on ANY GraphQL error, even a partial one (some
        # aliases fine, others NOT_FOUND/RESOURCE_LIMITS_EXCEEDED) --
        # stdout is still valid JSON with both `data` and `errors` in that
        # case, so parse regardless of returncode and only treat it as a
        # failure worth retrying if stdout isn't JSON at all.
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            stderr = proc.stderr.lower()
            if "rate limit" in stderr or "secondary rate" in stderr:
                raise RuntimeError(f"GitHub GraphQL rate limit: {proc.stderr[:300]}") from None
            # Transient connection hiccups (HTTP/2 stream resets, DNS
            # blips, etc.) -- worth a few retries before giving up, same
            # backoff-and-retry principle as the rate-limit sleep below.
            last_err = RuntimeError(f"gh api graphql failed (exit {proc.returncode}): {proc.stderr[:500]}")
            print(f"    [pr_text] transient error (attempt {attempt + 1}/{retries}): {proc.stderr[:200].strip()}")
            time.sleep(2 ** attempt)
    raise last_err


def _build_query(batch: list[PRRecord]) -> str:
    parts = [_FRAGMENT, "query {"]
    for i, r in enumerate(batch):
        owner, name = r.repo.split("/", 1)
        parts.append(
            f"  a{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            f"{{ pr: pullRequest(number: {r.pr_number}) {{ ...prFields }} }}"
        )
    parts.append("  rateLimit { cost remaining resetAt }")
    parts.append("}")
    return "\n".join(parts)


def _extract_comments(pr: dict) -> tuple[list[dict], bool]:
    comments: list[dict] = []
    truncated = False

    c = pr.get("comments") or {}
    for n in c.get("nodes") or []:
        comments.append({
            "kind": "issue_comment",
            "author": (n.get("author") or {}).get("login", ""),
            "body": n.get("body") or "",
            "created_at": n.get("createdAt"),
            "state": None, "path": None,
        })
    if (c.get("totalCount") or 0) > COMMENTS_PAGE:
        truncated = True

    r = pr.get("reviews") or {}
    for rev in r.get("nodes") or []:
        comments.append({
            "kind": "review",
            "author": (rev.get("author") or {}).get("login", ""),
            "body": rev.get("body") or "",
            "created_at": rev.get("createdAt"),
            "state": rev.get("state"), "path": None,
        })
        rc = rev.get("comments") or {}
        for n in rc.get("nodes") or []:
            comments.append({
                "kind": "review_comment",
                "author": (n.get("author") or {}).get("login", ""),
                "body": n.get("body") or "",
                "created_at": n.get("createdAt"),
                "state": None, "path": n.get("path"),
            })
        if (rc.get("totalCount") or 0) > REVIEW_COMMENTS_PAGE:
            truncated = True
    if (r.get("totalCount") or 0) > REVIEWS_PAGE:
        truncated = True

    return comments, truncated


def _fetch_batch(batch: list[PRRecord], depth: int = 0) -> dict[str, EnrichResult]:
    """Returns {record_id: EnrichResult}. Splits and retries on
    RESOURCE_LIMITS_EXCEEDED; NOT_FOUND (deleted/renamed/private repo or PR)
    is recorded as found=False, never retried."""
    if not batch:
        return {}

    resp = _gh_graphql(_build_query(batch))
    data = resp.get("data") or {}
    errors = resp.get("errors") or []

    err_by_alias: dict[str, str] = {}
    for e in errors:
        path = e.get("path") or []
        if path:
            err_by_alias[path[0]] = e.get("type", "UNKNOWN")

    results: dict[str, EnrichResult] = {}
    retry: list[PRRecord] = []

    for i, r in enumerate(batch):
        alias = f"a{i}"
        node = data.get(alias)
        pr = (node or {}).get("pr") if node else None

        if pr:
            comments, truncated = _extract_comments(pr)
            results[r.id] = EnrichResult(
                record_id=r.id, found=True,
                title=pr.get("title"), body=pr.get("body"),
                comments=comments, truncated=truncated,
            )
            continue

        err_type = err_by_alias.get(alias)
        if err_type == "RESOURCE_LIMITS_EXCEEDED" and depth < MAX_RETRY_DEPTH:
            retry.append(r)
        else:
            results[r.id] = EnrichResult(record_id=r.id, found=False)

    rate = data.get("rateLimit") or {}
    remaining = rate.get("remaining")
    if remaining is not None and remaining < 50:
        reset_at = rate.get("resetAt")
        if reset_at:
            reset_dt = datetime.strptime(reset_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            wait_s = max(0.0, (reset_dt - datetime.now(timezone.utc)).total_seconds()) + 10
            print(f"    [pr_text] rate limit low ({remaining} left), sleeping {wait_s:.0f}s")
            time.sleep(wait_s)

    if retry:
        mid = max(1, len(retry) // 2)
        results.update(_fetch_batch(retry[:mid], depth + 1))
        if len(retry) > 1:
            results.update(_fetch_batch(retry[mid:], depth + 1))

    return results


def _cache_path(cache_dir: Path) -> Path:
    return cache_dir / "pr_text.jsonl"


def _load_cache(cache_dir: Path) -> dict[str, EnrichResult]:
    path = _cache_path(cache_dir)
    if not path.exists():
        return {}
    out: dict[str, EnrichResult] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["record_id"]] = EnrichResult(**d)
    return out


def _append_cache(results: list[EnrichResult], cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with _cache_path(cache_dir).open("a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({
                "record_id": r.record_id, "found": r.found, "title": r.title,
                "body": r.body, "comments": r.comments, "truncated": r.truncated,
            }) + "\n")


def enrich_records(
    records: list[PRRecord],
    *,
    batch_size: int = BATCH_SIZE,
    cache_dir: Path | None = None,
) -> list[PRRecord]:
    """Mutates and returns records with title/pr_body_markdown/pr_comments
    filled in from GitHub GraphQL. Resumable via cache_dir -- a crash or
    interrupt only loses the current in-flight batch."""
    cache = _load_cache(cache_dir) if cache_dir else {}

    pending = [r for r in records if r.id not in cache]
    print(f"[pr_text] {len(records)} records, {len(records) - len(pending)} cached, {len(pending)} to fetch")

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        results = _fetch_batch(batch)
        if cache_dir:
            _append_cache(list(results.values()), cache_dir)
        cache.update(results)
        done = min(start + batch_size, len(pending))
        print(f"    fetched {done}/{len(pending)}")

    n_found = n_truncated = 0
    for r in records:
        res = cache.get(r.id)
        if res is None:
            continue
        r.text_enriched = True
        if res.found:
            n_found += 1
            r.title = res.title
            r.pr_body_markdown = res.body
            r.pr_comments = res.comments or []
            r.text_truncated = res.truncated
            if res.truncated:
                n_truncated += 1

    print(f"[pr_text] {n_found}/{len(records)} found, {n_truncated} truncated "
          f"(hit the {COMMENTS_PAGE}-comment/{REVIEWS_PAGE}-review page cap)")
    return records
