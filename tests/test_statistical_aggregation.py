from cwv_playbook_miner.aggregation.statistical import aggregate_patterns, to_technique_cluster
from cwv_playbook_miner.extraction.pattern_extract import ExtractedPattern


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


def test_controlled_family_merges_different_specific_techniques_without_judge() -> None:
    patterns = [
        _pattern("one/repo#1", "deep import one icon", broad_family="reduce-shipped-javascript"),
        _pattern("two/repo#2", "exclude tests from bundle", broad_family="reduce-shipped-javascript"),
        _pattern("three/repo#3", "remove unreachable frontend code", broad_family="reduce-shipped-javascript"),
    ]

    def unexpected_judge(*_args):
        raise AssertionError("family-normalized observations must not call the LLM judge")

    aggregates = aggregate_patterns(patterns, judge=unexpected_judge)

    assert len(aggregates) == 1
    assert aggregates[0].canonical_id == "reduce-shipped-javascript"
    assert aggregates[0].observation_count == 3
    assert aggregates[0].distinct_repo_count == 3
    assert aggregates[0].eligible
