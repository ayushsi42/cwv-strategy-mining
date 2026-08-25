from datetime import datetime

from cwv_playbook_miner.sourcing import gharchive_mine


def _event(hour: int) -> dict:
    return {
        "type": "IssueCommentEvent",
        "repo": {"name": f"example/repo-{hour}"},
        "actor": {"login": "lighthouse[bot]"},
        "payload": {
            "issue": {"number": hour, "pull_request": {}},
            "comment": {"body": "Lighthouse performance report"},
        },
        "created_at": f"2025-01-01T{hour:02d}:00:00Z",
    }


def _review_comment_event(actor: str, body: str, number: int = 7) -> dict:
    return {
        "type": "PullRequestReviewCommentEvent",
        "repo": {"name": "example/reviewed-repo"},
        "actor": {"login": actor},
        "payload": {
            "pull_request": {"number": number},
            "comment": {"body": body},
        },
        "created_at": "2025-01-01T00:00:00Z",
    }


def _review_event(actor: str, body: str, number: int = 8) -> dict:
    return {
        "type": "PullRequestReviewEvent",
        "repo": {"name": "example/reviewed-repo"},
        "actor": {"login": actor},
        "payload": {
            "pull_request": {"number": number},
            "review": {"body": body},
        },
        "created_at": "2025-01-01T00:00:00Z",
    }


def test_parallel_hour_scan_matches_sequential_scan() -> None:
    original = gharchive_mine.fetch_hour_events

    def fake_fetch(dt, type_filter=None):
        if dt.hour == 2:
            return None
        return iter([_event(dt.hour)])

    gharchive_mine.fetch_hour_events = fake_fetch
    try:
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 1, 4)
        sequential = gharchive_mine.scan_range(start, end, track_merges=False, workers=1)
        parallel = gharchive_mine.scan_range(start, end, track_merges=False, workers=4)
    finally:
        gharchive_mine.fetch_hour_events = original

    assert parallel.hours_scanned == sequential.hours_scanned == 3
    assert parallel.hours_skipped == sequential.hours_skipped == 1
    assert {(hit.repo, hit.pr_number, hit.source) for hit in parallel.comment_hits} == {
        (hit.repo, hit.pr_number, hit.source) for hit in sequential.comment_hits
    }


def _scan_single_hour(events: list[dict]):
    original = gharchive_mine.fetch_hour_events

    def fake_fetch(dt, type_filter=None):
        return iter(events)

    gharchive_mine.fetch_hour_events = fake_fetch
    try:
        return gharchive_mine.scan_range(
            datetime(2025, 1, 1), datetime(2025, 1, 1, 1), track_merges=False, workers=1,
        )
    finally:
        gharchive_mine.fetch_hour_events = original


def test_bot_report_via_review_events_uses_bot_template_path() -> None:
    result = _scan_single_hour([
        _review_comment_event("lighthouse[bot]", "Lighthouse performance report", number=7),
        _review_event("lighthouse[bot]", "Lighthouse performance report", number=8),
    ])
    hits = {(h.pr_number, h.source) for h in result.comment_hits}
    assert hits == {(7, "review_comment"), (8, "review")}


def test_human_marker_match_via_review_events() -> None:
    result = _scan_single_hour([
        _review_comment_event("real-reviewer", "nice, this drops LCP a lot", number=9),
        _review_event("real-reviewer", "reduces bundle size noticeably", number=10),
    ])
    hits = {(h.pr_number, h.source) for h in result.comment_hits}
    assert hits == {(9, "review_comment"), (10, "review")}


def test_non_matching_review_events_produce_no_hit() -> None:
    result = _scan_single_hour([
        _review_comment_event("lighthouse[bot]", "unrelated bot chatter", number=11),
        _review_event("real-reviewer", "looks good to me, merging", number=12),
    ])
    assert result.comment_hits == []


def test_human_flagged_candidates_excludes_bot_and_already_measured() -> None:
    hits = [
        gharchive_mine.CommentHit(repo="r", pr_number=1, actor="lighthouse[bot]",
                                   body="", created_at="", source="bot_comment"),
        gharchive_mine.CommentHit(repo="r", pr_number=2, actor="real-reviewer",
                                   body="reduces LCP", created_at="", source="review_comment"),
        gharchive_mine.CommentHit(repo="r", pr_number=3, actor="real-reviewer",
                                   body="reduces bundle size", created_at="", source="review"),
    ]
    assert gharchive_mine.human_flagged_candidates(hits) == {("r", 2), ("r", 3)}


def test_human_flagged_candidates_excludes_bot_hit_even_via_review_source() -> None:
    """Regression: a [bot]-suffixed actor's review/review_comment hit that
    coincidentally matched a narrow BOT_COMMENT_MARKERS substring (a valid
    bot-template-path candidate) must never also count as human-flagged --
    `source` alone doesn't distinguish who/how it matched, only the event
    type. Caught live: coderabbitai[bot]'s multi-thousand-char review dumps
    were leaking through as "human-flagged" before this filter existed."""
    hits = [
        gharchive_mine.CommentHit(repo="r", pr_number=5, actor="coderabbitai[bot]",
                                   body="...reviewing an unrelated bundle size mention...",
                                   created_at="", source="review_comment"),
    ]
    assert gharchive_mine.human_flagged_candidates(hits) == set()


def test_is_bot_actor_covers_known_bare_login_bots() -> None:
    """Regression: GitHub's Copilot PR reviewer posts as plain login
    "Copilot" (no [bot] suffix) -- confirmed live its auto-generated
    "## Pull request overview" summaries were slipping past is_bot_actor
    into the human-signal marker path."""
    assert gharchive_mine.is_bot_actor("Copilot")
    assert gharchive_mine.is_bot_actor("copilot")
    assert not gharchive_mine.is_bot_actor("real-reviewer")


def test_human_comment_matches_markers_rejects_long_bodies() -> None:
    """Automated review-tool dumps are long enough that a broad marker
    regex matches by chance even on an unrelated PR -- confirmed live
    against real CodeRabbit-style output. A short genuine human comment
    with the same marker still matches."""
    long_body = "unrelated review notes. " * 100 + "mentions lazy load once"
    assert len(long_body) > gharchive_mine.HUMAN_SIGNAL_MAX_BODY_LEN
    assert not gharchive_mine.human_comment_matches_markers(long_body)
    assert gharchive_mine.human_comment_matches_markers("nice, this reduces bundle size")
