from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cwv_playbook_miner.extraction.pattern_extract import _to_pattern, extract_patterns
from cwv_playbook_miner.extraction.pr_record import PRRecord


def _record(index: int) -> PRRecord:
    return PRRecord(
        id=f"org/repo-{index}#{index}", repo=f"org/repo-{index}", pr_number=index,
        signal_type="perf_improvement", metric_key="performance",
        before=70, after=80, delta=10, title=f"Optimize route {index}",
        changed_files=[{"filename": "app.js", "patch": "+ import('./secondary')"}],
    )


def _response_for_prompt(_system, user, **_kwargs):
    import json

    inputs = json.loads(user.split("\n", 1)[1])
    return {"results": [{
        "source_id": item["source_id"],
        "is_page_performance": True,
        "rejection_reason": "",
        "broad_family": "reduce-shipped-javascript",
        "technique": "code split secondary route",
        "problem_symptom": "unused JavaScript",
        "code_pattern": "load the secondary route on demand",
        "why_it_works": "reduces initial JavaScript",
        "framework_hint": "any",
        "applicable_signal": "unused JavaScript",
        "mechanism": "defer",
        "affected_resource": "main-thread-js",
        "render_phase": "initial-load",
    } for item in inputs]}


def test_extraction_batches_and_reuses_per_record_cache() -> None:
    records = [_record(index) for index in range(5)]
    with TemporaryDirectory() as directory:
        cache_dir = Path(directory)
        with patch(
            "cwv_playbook_miner.extraction.pattern_extract.complete_json",
            side_effect=_response_for_prompt,
        ) as completion:
            first = extract_patterns(
                records, "openai", "test-model", 30,
                concurrency=2, batch_size=2, cache_dir=cache_dir,
            )
            assert completion.call_count == 3
            second = extract_patterns(
                records, "openai", "test-model", 30,
                concurrency=2, batch_size=4, cache_dir=cache_dir,
            )
            assert completion.call_count == 3

    assert len(first) == len(second) == 5


def test_family_guard_rejects_fallback_request_as_cache_reuse() -> None:
    extracted = _response_for_prompt(
        "", "ignored\n" + __import__("json").dumps([{"source_id": "org/repo-1#1"}]),
    )["results"][0]
    extracted.update({
        "broad_family": "reuse-cache-and-data",
        "technique": "fallback request to alternate API",
        "mechanism": "make a second request after failure",
        "why_it_works": "the second request can return usable data",
    })

    assert _to_pattern(_record(1), extracted) is None
