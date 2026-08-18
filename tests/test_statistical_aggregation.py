import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cwv_playbook_miner.aggregation.statistical import (
    aggregate_patterns, resolve_substrategy_matches, to_parent_strategy_clusters,
    to_technique_cluster,
)
from cwv_playbook_miner.extraction.pattern_extract import ExtractedPattern
from cwv_playbook_miner.taxonomy import write_parent_proposals


def _pattern(
    source: str,
    technique: str,
    signal_type: str = "perf_improvement",
    metric: str = "performance",
    delta: float = 10,
    mechanism: str = "",
    affected_resource: str = "",
    render_phase: str = "",
    broad_family: str = "",
    parent_strategy: str = "layout-stability",
    sub_strategy: str | None = None,
) -> ExtractedPattern:
    return ExtractedPattern(
        source_id=source,
        source_repo=source.rsplit("#", 1)[0],
        signal_type=signal_type,
        technique=technique,
        problem_symptom="slow page",
        code_pattern="defer the offscreen image",
        why_it_works="removes work from initial rendering",
        framework_hint="any",
        applicable_signal="offscreen images",
        measured_delta={"metric_key": metric, "delta": delta},
        mechanism=mechanism,
        affected_resource=affected_resource,
        render_phase=render_phase,
        broad_family=broad_family,
        parent_strategy=parent_strategy,
        sub_strategy=sub_strategy or technique,
    )


def test_common_observations_become_one_eligible_aggregate() -> None:
    patterns = [
        _pattern("one/repo#1", "Defer offscreen images"),
        _pattern("two/repo#2", "defer offscreen images"),
        _pattern("three/repo#3", "Defer offscreen-images"),
    ]
    aggregates = aggregate_patterns(patterns)

    assert len(aggregates) == 1
    item = aggregates[0]
    assert item.observation_count == 3
    assert item.distinct_repo_count == 3
    assert item.eligible
    assert to_technique_cluster(item).confidence == "medium"


def test_llm_judge_is_only_used_for_borderline_alias() -> None:
    patterns = [
        _pattern("one/repo#1", "defer offscreen images"),
        _pattern("two/repo#2", "defer below fold images"),
    ]
    calls = []

    def judge(pattern, aggregate):
        calls.append((pattern.technique, aggregate.canonical_name))
        return True

    aggregates = aggregate_patterns(
        patterns, judge=judge, min_observations=1, min_repos=1,
        borderline_threshold=0.2,
    )

    assert len(aggregates) == 1
    assert len(calls) == 1
    assert "defer below fold images" in aggregates[0].aliases


def test_structured_signature_retrieves_differently_named_techniques() -> None:
    patterns = [
        _pattern(
            "one/repo#1", "delay invisible media",
            mechanism="defer", affected_resource="offscreen-images", render_phase="initial-load",
        ),
        _pattern(
            "two/repo#2", "lazy load below fold pictures",
            mechanism="defer", affected_resource="offscreen-images", render_phase="initial-load",
        ),
    ]
    calls = []

    def judge(pattern, aggregate):
        calls.append((pattern.technique, aggregate.canonical_id))
        return True

    aggregates = aggregate_patterns(
        patterns, judge=judge, min_observations=1, min_repos=1,
        auto_merge_threshold=0.95, borderline_threshold=0.3,
    )

    assert len(aggregates) == 1
    assert len(calls) == 1


def test_metrics_are_summarized_separately() -> None:
    patterns = [
        _pattern("one/repo#1", "reduce render work", metric="performance", delta=20),
        _pattern("two/repo#2", "reduce render work", metric="performance", delta=10),
        _pattern("three/repo#3", "reduce render work", metric="lcp_ms", delta=-400),
    ]
    item = aggregate_patterns(patterns)[0]

    assert item.metric_summaries["performance"]["median"] == 15
    assert item.metric_summaries["lcp_ms"]["median"] == 400


def test_directional_inconsistency_keeps_cluster_provisional() -> None:
    patterns = [
        _pattern("one/repo#1", "reduce render work"),
        _pattern("two/repo#2", "reduce render work"),
        _pattern("three/repo#3", "reduce render work", signal_type="perf_decrease"),
    ]
    item = aggregate_patterns(patterns, min_consistency=0.7)[0]

    assert item.directional_consistency == 0.6667
    assert not item.eligible


def test_prior_registry_preserves_canonical_id_across_rebuilds() -> None:
    initial = aggregate_patterns(
        [_pattern("one/repo#1", "defer offscreen images")],
        min_observations=1, min_repos=1,
    )
    canonical_id = initial[0].canonical_id
    rebuilt = aggregate_patterns(
        [
            _pattern("one/repo#1", "defer offscreen images"),
            _pattern("two/repo#2", "defer offscreen images"),
        ],
        prior=initial,
        min_observations=1,
        min_repos=1,
    )

    assert len(rebuilt) == 1
    assert rebuilt[0].canonical_id == canonical_id
    assert rebuilt[0].observation_count == 2


def test_prior_registry_persists_structured_signature_for_new_aliases() -> None:
    initial = aggregate_patterns(
        [_pattern(
            "one/repo#1", "delay invisible media",
            mechanism="defer", affected_resource="offscreen-images", render_phase="initial-load",
        )],
        min_observations=1, min_repos=1,
    )
    calls = []

    def judge(pattern, aggregate):
        calls.append(aggregate.canonical_id)
        return True

    rebuilt = aggregate_patterns(
        [_pattern(
            "two/repo#2", "lazy pictures beneath viewport",
            mechanism="defer", affected_resource="offscreen-images", render_phase="initial-load",
        )],
        prior=initial,
        judge=judge,
        min_observations=1,
        min_repos=1,
        auto_merge_threshold=0.95,
        borderline_threshold=0.3,
    )

    assert len(rebuilt) == 1
    assert rebuilt[0].canonical_id == initial[0].canonical_id
    assert len(calls) == 1


def test_literal_null_techniques_are_not_aggregated() -> None:
    assert aggregate_patterns([_pattern("one/repo#1", "null")]) == []


def test_parent_and_shared_sub_strategy_merge_specific_variants_without_judge() -> None:
    patterns = [
        _pattern("one/repo#1", "deep import one icon", parent_strategy="javascript-delivery", sub_strategy="remove unused javascript"),
        _pattern("two/repo#2", "exclude tests from bundle", parent_strategy="javascript-delivery", sub_strategy="remove unused javascript"),
        _pattern("three/repo#3", "remove unreachable frontend code", parent_strategy="javascript-delivery", sub_strategy="remove unused javascript"),
    ]

    def unexpected_judge(*_args):
        raise AssertionError("family-normalized observations must not call the LLM judge")

    aggregates = aggregate_patterns(patterns, judge=unexpected_judge)

    assert len(aggregates) == 1
    assert aggregates[0].canonical_id == "javascript-delivery--remove-unused-javascript"
    assert aggregates[0].parent_strategy == "javascript-delivery"
    assert aggregates[0].observation_count == 3
    assert aggregates[0].distinct_repo_count == 3
    assert aggregates[0].eligible


def test_single_observation_stays_provisional() -> None:
    item = aggregate_patterns([
        _pattern("one/repo#1", "reserve async panel space", sub_strategy="reserve space for async content"),
    ], min_observations=1, min_repos=1)[0]

    assert item.status == "provisional"
    assert not item.eligible


def test_identical_sub_strategy_names_under_different_parents_never_merge() -> None:
    patterns = [
        _pattern("one/repo#1", "defer work", parent_strategy="javascript-delivery", sub_strategy="defer optional work"),
        _pattern("two/repo#2", "defer work", parent_strategy="third-party-cost", sub_strategy="defer optional work"),
    ]
    assert len(aggregate_patterns(patterns, min_observations=1, min_repos=1)) == 2


def test_ambiguous_sub_strategy_resolution_is_batched_within_parent() -> None:
    patterns = [
        _pattern(
            "one/repo#1", "delay invisible media", parent_strategy="image-delivery",
            sub_strategy="defer offscreen images", mechanism="defer",
            affected_resource="offscreen images", render_phase="initial-load",
        ),
        _pattern(
            "two/repo#2", "lazy pictures beneath viewport", parent_strategy="image-delivery",
            sub_strategy="lazy load below fold pictures", mechanism="defer",
            affected_resource="offscreen images", render_phase="initial-load",
        ),
    ]

    def resolve(_system, user, **_kwargs):
        requests = json.loads(user)
        results = []
        for request in requests:
            match = next(
                (candidate for candidate in request["candidates"] if candidate["name"] == "defer offscreen images"),
                None,
            )
            results.append({
                "source_id": request["source_id"],
                "canonical_id": match["canonical_id"] if match else None,
            })
        return {"results": results}

    with patch("cwv_playbook_miner.aggregation.statistical.complete_json", side_effect=resolve) as completion:
        resolve_substrategy_matches(patterns, [], "openai", "test", 30)

    assert completion.call_count == 1
    initial = aggregate_patterns(patterns, min_observations=1, min_repos=1)
    assert len(initial) == 1
    raw_alias = _pattern(
        "three/repo#3", "pictures under viewport", parent_strategy="image-delivery",
        sub_strategy="lazy load below fold pictures", mechanism="defer",
        affected_resource="offscreen images", render_phase="initial-load",
    )
    rebuilt = aggregate_patterns([raw_alias], prior=initial, min_observations=1, min_repos=1)
    assert len(rebuilt) == 1
    assert rebuilt[0].canonical_id == initial[0].canonical_id


def test_unknown_parent_proposals_require_review_and_repetition() -> None:
    patterns = [
        _pattern("one/repo#1", "stream edge output", parent_strategy="unclassified", sub_strategy="stream edge output"),
        _pattern("two/repo#2", "stream edge output", parent_strategy="unclassified", sub_strategy="stream edge output"),
        _pattern("three/repo#3", "stream edge output", parent_strategy="unclassified", sub_strategy="stream edge output"),
    ]
    for pattern in patterns:
        pattern.proposed_parent_strategy = "edge delivery architecture"
    with TemporaryDirectory() as directory:
        path = Path(directory) / "proposals.jsonl"
        assert write_parent_proposals(patterns, path) == 1
        proposal = json.loads(path.read_text())

    assert proposal["promotion_ready"] is True
    assert proposal["status"] == "human-review"
    assert aggregate_patterns(patterns) == []


def test_parent_candidate_combines_children_but_requires_an_active_child() -> None:
    patterns = [
        _pattern("one/repo#1", "remove dependency", parent_strategy="network-payload", sub_strategy="remove unused shipped code"),
        _pattern("two/repo#2", "prune dead code", parent_strategy="network-payload", sub_strategy="remove unused shipped code"),
        _pattern("three/repo#3", "exclude source maps", parent_strategy="network-payload", sub_strategy="exclude non-runtime assets"),
    ]
    aggregates = aggregate_patterns(patterns)
    clusters = to_parent_strategy_clusters(aggregates)

    assert len(clusters) == 1
    assert clusters[0].normalized_key == "network-payload"
    assert clusters[0].frequency == 3
    assert set(clusters[0].aliases) == {"remove unused shipped code", "exclude non-runtime assets"}


def test_parent_singletons_cannot_manufacture_candidate() -> None:
    patterns = [
        _pattern("one/repo#1", "one", parent_strategy="network-payload", sub_strategy="remove unused code"),
        _pattern("two/repo#2", "two", parent_strategy="network-payload", sub_strategy="compress json"),
        _pattern("three/repo#3", "three", parent_strategy="network-payload", sub_strategy="strip source maps"),
    ]
    assert to_parent_strategy_clusters(aggregate_patterns(patterns)) == []
