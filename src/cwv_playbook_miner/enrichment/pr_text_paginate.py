"""Full (non-truncated) re-fetch for PRs that hit a page cap in pr_text.py's
batched fetch (>50 comments, >30 reviews, or >30 inline comments on a single
review). This one's per-PR, not batched via aliases -- pagination needs a
cursor per connection, which doesn't compose across many PRs in one query
the way the first pass's aliasing did. Only worth doing for the ~10% of
records that actually got truncated; the batched aliased approach in
pr_text.py stays the right tool for the other 90%.

Page size 100 here (vs 50/30 in the first pass) since a single-PR query has
nowhere near the complexity budget pressure that ~40-PRs-in-one-query had --
that's what caused RESOURCE_LIMITS_EXCEEDED in the first pass, and a lone
PR's connections are nowhere close to that ceiling.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

MAX_PAGES = 50  # safety cap against a pathological PR -- 50 * 100 = 5,000 reviews/comments

_PR_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $commentsAfter: String, $reviewsAfter: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      title
      body
      comments(first: 100, after: $commentsAfter) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes { body createdAt author { login } }
      }
      reviews(first: 100, after: $reviewsAfter) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes {
          id body state createdAt author { login }
          comments(first: 100) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes { body path createdAt author { login } }
          }
        }
      }
    }
  }
}
"""

_REVIEW_COMMENTS_QUERY = """
query($id: ID!, $after: String) {
  node(id: $id) {
    ... on PullRequestReview {
      comments(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { body path createdAt author { login } }
      }
    }
  }
}
"""


@dataclass
class EnrichResult:
    record_id: str
    found: bool
    title: str | None = None
    body: str | None = None
    comments: list[dict] | None = None
    truncated: bool = False


def _gql(query: str, variables: dict, timeout: int = 60, retries: int = 4) -> dict:
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        if v is None:
            continue
        flag = "-F" if isinstance(v, int) else "-f"
        args += [flag, f"{k}={v}"]

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            last_err = exc
            time.sleep(2 ** attempt)
            continue
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            stderr = proc.stderr.lower()
            if "rate limit" in stderr or "secondary rate" in stderr:
                raise RuntimeError(f"GitHub GraphQL rate limit: {proc.stderr[:300]}") from None
            last_err = RuntimeError(f"gh api graphql failed (exit {proc.returncode}): {proc.stderr[:500]}")
            print(f"    [pr_text_paginate] transient error (attempt {attempt + 1}/{retries}): {proc.stderr[:200].strip()}")
            time.sleep(2 ** attempt)
    raise last_err


def fetch_full_pr(repo: str, pr_number: int) -> EnrichResult:
    record_id = f"{repo}#{pr_number}"
    owner, name = repo.split("/", 1)

    title = body = None
    issue_comments: list[dict] = []
    # review_id -> (review dict, list of its inline comments)
    reviews: dict[str, tuple[dict, list[dict]]] = {}
    review_order: list[str] = []

    comments_after = reviews_after = None
    hit_safety_cap = False

    for page in range(MAX_PAGES):
        resp = _gql(_PR_QUERY, {
            "owner": owner, "name": name, "number": pr_number,
            "commentsAfter": comments_after, "reviewsAfter": reviews_after,
        })
        data = resp.get("data") or {}
        errors = resp.get("errors") or []
        repo_node = data.get("repository")
        pr = (repo_node or {}).get("pullRequest") if repo_node else None

        if pr is None:
            types = {e.get("type") for e in errors}
            if "NOT_FOUND" in types:
                return EnrichResult(record_id=record_id, found=False)
            raise RuntimeError(f"unexpected empty response for {record_id}: {errors}")

        if title is None:
            title = pr.get("title")
            body = pr.get("body")

        c = pr["comments"]
        for n in c["nodes"]:
            issue_comments.append({
                "kind": "issue_comment",
                "author": (n.get("author") or {}).get("login", ""),
                "body": n.get("body") or "", "created_at": n.get("createdAt"),
                "state": None, "path": None,
            })
        c_more = c["pageInfo"]["hasNextPage"]
        if c_more:
            comments_after = c["pageInfo"]["endCursor"]

        r = pr["reviews"]
        for rev in r["nodes"]:
            rid = rev["id"]
            if rid not in reviews:
                review_order.append(rid)
                inline: list[dict] = []
                for n in (rev.get("comments") or {}).get("nodes") or []:
                    inline.append({
                        "kind": "review_comment",
                        "author": (n.get("author") or {}).get("login", ""),
                        "body": n.get("body") or "", "created_at": n.get("createdAt"),
                        "state": None, "path": n.get("path"),
                    })
                reviews[rid] = (rev, inline)
                if (rev.get("comments") or {}).get("pageInfo", {}).get("hasNextPage"):
                    _paginate_review_comments(rid, rev["comments"]["pageInfo"]["endCursor"], inline)
        r_more = r["pageInfo"]["hasNextPage"]
        if r_more:
            reviews_after = r["pageInfo"]["endCursor"]

        if not c_more and not r_more:
            break
    else:
        hit_safety_cap = True

    comments: list[dict] = list(issue_comments)
    for rid in review_order:
        rev, inline = reviews[rid]
        comments.append({
            "kind": "review",
            "author": (rev.get("author") or {}).get("login", ""),
            "body": rev.get("body") or "", "created_at": rev.get("createdAt"),
            "state": rev.get("state"), "path": None,
        })
        comments.extend(inline)

    return EnrichResult(
        record_id=record_id, found=True, title=title, body=body,
        comments=comments, truncated=hit_safety_cap,
    )


def _paginate_review_comments(review_id: str, after: str | None, into: list[dict]) -> None:
    for _ in range(MAX_PAGES):
        resp = _gql(_REVIEW_COMMENTS_QUERY, {"id": review_id, "after": after})
        node = (resp.get("data") or {}).get("node") or {}
        rc = node.get("comments") or {}
        for n in rc.get("nodes") or []:
            into.append({
                "kind": "review_comment",
                "author": (n.get("author") or {}).get("login", ""),
                "body": n.get("body") or "", "created_at": n.get("createdAt"),
                "state": None, "path": n.get("path"),
            })
        page_info = rc.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return
        after = page_info.get("endCursor")


def _cache_path(cache_dir: Path) -> Path:
    return cache_dir / "pr_text_full.jsonl"


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


def _append_cache(result: EnrichResult, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with _cache_path(cache_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "record_id": result.record_id, "found": result.found, "title": result.title,
            "body": result.body, "comments": result.comments, "truncated": result.truncated,
        }) + "\n")


def refetch_truncated(records, *, cache_dir: Path | None = None):
    """Full re-fetch, in place, for every record with text_truncated=True.
    Resumable via cache_dir."""
    cache = _load_cache(cache_dir) if cache_dir else {}
    targets = [r for r in records if r.text_truncated]
    pending = [r for r in targets if r.id not in cache]
    print(f"[pr_text_paginate] {len(targets)} truncated records, "
          f"{len(targets) - len(pending)} cached, {len(pending)} to re-fetch")

    for i, r in enumerate(pending, 1):
        result = fetch_full_pr(r.repo, r.pr_number)
        cache[r.id] = result
        if cache_dir:
            _append_cache(result, cache_dir)
        if i % 25 == 0 or i == len(pending):
            print(f"    re-fetched {i}/{len(pending)}")

    n_updated = n_still_capped = 0
    for r in targets:
        res = cache.get(r.id)
        if res is None or not res.found:
            continue
        r.title = res.title
        r.pr_body_markdown = res.body
        r.pr_comments = res.comments or []
        r.text_truncated = res.truncated
        n_updated += 1
        if res.truncated:
            n_still_capped += 1

    print(f"[pr_text_paginate] {n_updated}/{len(targets)} fully re-fetched, "
          f"{n_still_capped} still capped (hit the {MAX_PAGES}-page safety limit)")
    return records
