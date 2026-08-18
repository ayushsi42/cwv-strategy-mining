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
    assert {(hit.repo, hit.pr_number) for hit in parallel.comment_hits} == {
        (hit.repo, hit.pr_number) for hit in sequential.comment_hits
    }
