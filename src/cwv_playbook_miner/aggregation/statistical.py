"""Canonical, incremental-style aggregation over extracted PR techniques.

The stage is rebuilt from the complete extracted-pattern JSONL on each run,
which makes it idempotent and prevents double-counting after backfill resume.
Only sufficient statistics and bounded representative samples are persisted;
raw PR observations remain in the extraction JSONL files.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Callable

from cwv_playbook_miner.extraction.cluster import TechniqueCluster, normalize_technique
from cwv_playbook_miner.extraction.pattern_extract import ExtractedPattern
from cwv_playbook_miner.taxonomy import PARENT_STRATEGIES
from cwv_playbook_miner.llm.client import LLMError, complete_json


MAX_EFFECT_SAMPLE = 256
MAX_REPRESENTATIVES = 5
STOPWORDS = {
    "a", "an", "and", "the", "to", "for", "from", "in", "of", "on",
    "with", "by", "during", "when", "into",
}


def _tokens(value: str) -> set[str]:
    return {token for token in normalize_technique(value).split() if token not in STOPWORDS}


def lexical_similarity(left: str, right: str) -> float:
    """Token Jaccard used only for candidate retrieval, never final semantics."""
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _match_text(item: ExtractedPattern | dict) -> str:
    get = (lambda key: getattr(item, key, "")) if isinstance(item, ExtractedPattern) else (lambda key: item.get(key, ""))
    return " ".join(
        str(get(key) or "")
        for key in ("sub_strategy", "technique", "mechanism", "affected_resource", "render_phase", "applicable_signal")
    )


def _aggregate_match_texts(item: "TechniqueAggregate") -> list[str]:
    examples = item.representative_improvements + item.representative_regressions
    return [
        item.canonical_name, *item.aliases, *item.signature_aliases,
        *(_match_text(example) for example in examples),
    ]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unnamed-technique"


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 4)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def _bounded_by_source(items: list[dict], limit: int) -> list[dict]:
    unique = {item["source_id"]: item for item in items}
    return sorted(
        unique.values(),
        key=lambda item: hashlib.sha1(item["source_id"].encode()).hexdigest(),
    )[:limit]


@dataclass
class TechniqueAggregate:
    canonical_id: str
    canonical_name: str
    parent_strategy: str = ""
    status: str = "provisional"
    aliases: list[str] = field(default_factory=list)
    signature_aliases: list[str] = field(default_factory=list)
    observation_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    repo_counts: dict[str, int] = field(default_factory=dict)
    framework_counts: dict[str, int] = field(default_factory=dict)
    signal_counts: dict[str, int] = field(default_factory=dict)
    metric_counts: dict[str, int] = field(default_factory=dict)
    metric_effect_samples: dict[str, list[float]] = field(default_factory=dict)
    metric_summaries: dict[str, dict] = field(default_factory=dict)
    representative_improvements: list[dict] = field(default_factory=list)
    representative_regressions: list[dict] = field(default_factory=list)
    median_abs_delta: float | None = None
    delta_p25: float | None = None
    delta_p75: float | None = None
    directional_consistency: float = 0.0
    confidence: str = "provisional"
    eligible: bool = False

    @property
    def distinct_repo_count(self) -> int:
        return len(self.repo_counts)

    def finalize(
        self, min_observations: int, min_repos: int, min_consistency: float,
    ) -> None:
        self.metric_summaries = {}
        for metric, values in self.metric_effect_samples.items():
            sample = [abs(value) for value in values]
            self.metric_summaries[metric] = {
                "count": len(sample),
                "p25": _quantile(sample, 0.25),
                "median": round(median(sample), 4) if sample else None,
                "p75": _quantile(sample, 0.75),
            }
        dominant_metric = max(self.metric_counts, key=self.metric_counts.get) if self.metric_counts else None
        sample = [abs(value) for value in self.metric_effect_samples.get(dominant_metric, [])]
        self.median_abs_delta = round(median(sample), 4) if sample else None
        self.delta_p25 = _quantile(sample, 0.25)
        self.delta_p75 = _quantile(sample, 0.75)
        directional = self.positive_count + self.negative_count
        self.directional_consistency = round(
            self.positive_count / directional, 4,
        ) if directional else 0.0
        self.status = (
            "active" if self.observation_count >= 2 and self.distinct_repo_count >= 2
            else "provisional"
        )
        self.eligible = (
            self.status == "active"
            and
            self.observation_count >= min_observations
            and self.distinct_repo_count >= min_repos
            and self.positive_count > 0
            and self.directional_consistency >= min_consistency
        )
        if not self.eligible:
            self.confidence = "provisional"
        elif (
            self.observation_count >= 10
            and self.distinct_repo_count >= 5
            and self.directional_consistency >= 0.8
        ):
            self.confidence = "high"
        else:
            self.confidence = "medium"


def _representative(pattern: ExtractedPattern) -> dict:
    return {
        "source_id": pattern.source_id,
        "source_repo": pattern.source_repo,
        "technique": pattern.technique,
        "parent_strategy": pattern.parent_strategy,
        "sub_strategy": pattern.sub_strategy,
        "problem_symptom": pattern.problem_symptom,
        "code_pattern": pattern.code_pattern,
        "why_it_works": pattern.why_it_works,
        "framework_hint": pattern.framework_hint,
        "applicable_signal": pattern.applicable_signal,
        "mechanism": pattern.mechanism,
        "affected_resource": pattern.affected_resource,
        "render_phase": pattern.render_phase,
        "measured_delta": pattern.measured_delta,
    }


def _add_observation(aggregate: TechniqueAggregate, pattern: ExtractedPattern) -> None:
    aggregate.observation_count += 1
    signature = normalize_technique(_match_text(pattern))
    aggregate.signature_aliases = sorted(set([*aggregate.signature_aliases, signature]))[:20]
    if pattern.signal_type == "perf_improvement":
        aggregate.positive_count += 1
        aggregate.representative_improvements.append(_representative(pattern))
        aggregate.representative_improvements = _bounded_by_source(
            aggregate.representative_improvements, MAX_REPRESENTATIVES,
        )
    elif pattern.signal_type == "perf_decrease":
        aggregate.negative_count += 1
        aggregate.representative_regressions.append(_representative(pattern))
        aggregate.representative_regressions = _bounded_by_source(
            aggregate.representative_regressions, MAX_REPRESENTATIVES,
        )
    aggregate.repo_counts[pattern.source_repo] = aggregate.repo_counts.get(pattern.source_repo, 0) + 1
    framework = pattern.framework_hint or "any"
    aggregate.framework_counts[framework] = aggregate.framework_counts.get(framework, 0) + 1
    if pattern.applicable_signal:
        aggregate.signal_counts[pattern.applicable_signal] = aggregate.signal_counts.get(pattern.applicable_signal, 0) + 1
    metric = pattern.measured_delta.get("metric_key")
    if metric:
        aggregate.metric_counts[metric] = aggregate.metric_counts.get(metric, 0) + 1
    delta = pattern.measured_delta.get("delta")
    if metric and isinstance(delta, (int, float)):
        effect_items_by_metric = getattr(aggregate, "_effect_items_by_metric", {})
        effect_items = [
            {"source_id": item["source_id"], "value": item["value"]}
            for item in effect_items_by_metric.get(metric, [])
        ]
        effect_items.append({"source_id": pattern.source_id, "value": float(delta)})
        effect_items = _bounded_by_source(effect_items, MAX_EFFECT_SAMPLE)
        effect_items_by_metric[metric] = effect_items
        aggregate._effect_items_by_metric = effect_items_by_metric  # transient, not serialized
        aggregate.metric_effect_samples[metric] = [item["value"] for item in effect_items]


BorderlineJudge = Callable[[ExtractedPattern, TechniqueAggregate], bool]


def resolve_substrategy_matches(
    patterns: list[ExtractedPattern], prior: list[TechniqueAggregate],
    backend: str, model: str | None, timeout: int, batch_size: int = 12,
) -> int:
    """Batch ambiguous sub-strategy aliases within their assigned parent.

    The resolver never changes a parent and never creates one. It only maps a
    proposed sub-strategy onto one of a small set of existing/current sibling
    names. Returning null leaves the observation as a provisional new child.
    """
    known_by_parent: dict[str, dict[str, dict]] = {}
    for item in prior:
        if item.parent_strategy in PARENT_STRATEGIES:
            bucket = known_by_parent.setdefault(item.parent_strategy, {})
            bucket[item.canonical_name] = {
                "canonical_id": item.canonical_id,
                "texts": _aggregate_match_texts(item),
                "status": item.status,
            }
            for alias in item.aliases:
                bucket.setdefault(alias, {
                    "canonical_id": item.canonical_id,
                    "texts": _aggregate_match_texts(item),
                    "status": item.status,
                })
    for pattern in patterns:
        if pattern.parent_strategy in PARENT_STRATEGIES:
            known_by_parent.setdefault(pattern.parent_strategy, {}).setdefault(pattern.sub_strategy, {
                "canonical_id": f"proposal:{normalize_technique(pattern.sub_strategy)}",
                "texts": [_match_text(pattern)],
                "status": "current",
            })

    unresolved = []
    for pattern in patterns:
        parent = pattern.parent_strategy
        proposed = normalize_technique(pattern.sub_strategy)
        siblings = known_by_parent.get(parent, {})
        exact = [
            (name, sibling) for name, sibling in siblings.items()
            if normalize_technique(name) == proposed
        ]
        active_exact = [item for item in exact if item[1]["status"] == "active"]
        if active_exact:
            pattern.sub_strategy_aliases = sorted(set([
                *pattern.sub_strategy_aliases, pattern.sub_strategy,
            ]))
            pattern.sub_strategy = active_exact[0][0]
            continue
        prior_self_ids = {
            sibling["canonical_id"] for _name, sibling in exact
            if sibling["status"] == "provisional"
        }
        candidates = []
        pattern_text = _match_text(pattern)
        for name, sibling in siblings.items():
            if normalize_technique(name) == proposed:
                continue
            if sibling["canonical_id"] in prior_self_ids:
                continue
            score = max(lexical_similarity(pattern_text, text) for text in sibling["texts"])
            if score >= 0.12:
                candidates.append({
                    "name": name, "canonical_id": sibling["canonical_id"], "score": round(score, 3),
                })
        best_by_id = {}
        for candidate in candidates:
            current = best_by_id.get(candidate["canonical_id"])
            if current is None or candidate["score"] > current["score"]:
                best_by_id[candidate["canonical_id"]] = candidate
        candidates = list(best_by_id.values())
        candidates.sort(key=lambda item: (-item["score"], item["name"]))
        if candidates:
            unresolved.append({
                "pattern": pattern,
                "payload": {
                    "source_id": pattern.source_id,
                    "parent_strategy": parent,
                    "proposed_sub_strategy": pattern.sub_strategy,
                    "mechanism": pattern.mechanism,
                    "affected_resource": pattern.affected_resource,
                    "render_phase": pattern.render_phase,
                    "why_it_works": pattern.why_it_works,
                    "candidates": candidates[:5],
                },
            })

    system = """Resolve reusable web-performance sub-strategy aliases. Each item already has a fixed parent strategy. Match only the same actionable intervention with compatible mechanism, target resource, render phase, applicability gate, and failure modes. Framework/component names may differ. Do not merge merely because both reduce bytes, both use caching, or improve the same metric. Examples: middleware-fetched user reuse and request-scoped authenticated user reuse may match; ETag response validation must not merge with authenticated user reuse; excluding package metadata must not merge with removing runtime JavaScript dependencies. Never change the parent. Return strict JSON: {"results":[{"source_id":"...","canonical_id":"one supplied candidate id or null"}]}."""
    resolved = 0
    for start in range(0, len(unresolved), batch_size):
        batch = unresolved[start:start + batch_size]
        try:
            response = complete_json(
                system, json.dumps([item["payload"] for item in batch]),
                backend=backend, model=model, timeout=timeout,
            )
        except LLMError as exc:
            print(f"    sub-strategy resolver batch failed: {exc}; leaving proposals separate")
            continue
        decisions = {
            item.get("source_id"): item.get("canonical_id")
            for item in response.get("results", []) if isinstance(item, dict)
        }
        for item in batch:
            pattern = item["pattern"]
            decision = decisions.get(pattern.source_id)
            allowed = {candidate["canonical_id"]: candidate["name"] for candidate in item["payload"]["candidates"]}
            if decision in allowed:
                pattern.sub_strategy_aliases = sorted(set([
                    *pattern.sub_strategy_aliases, pattern.sub_strategy,
                ]))
                pattern.sub_strategy = allowed[decision]
                resolved += 1
    if unresolved:
        print(f"  sub-strategy resolver: {len(unresolved)} ambiguous observation(s), {resolved} alias match(es), {math.ceil(len(unresolved) / batch_size)} LLM batch(es)")
    return resolved


def make_llm_judge(backend: str, model: str | None, timeout: int) -> BorderlineJudge:
    system = """Decide whether two web-performance technique descriptions represent the same reusable mechanism. Names may differ. They are the same only when mechanism, affected resource/work, render phase, and trigger signal are compatible. Related outcomes alone are insufficient. Return strict JSON: {"same_technique": true|false, "reason": "one sentence"}."""

    def judge(pattern: ExtractedPattern, aggregate: TechniqueAggregate) -> bool:
        examples = aggregate.representative_improvements + aggregate.representative_regressions
        user = f"""New observation:
technique: {pattern.technique}
mechanism: {pattern.why_it_works}
normalized mechanism: {pattern.mechanism}
affected resource: {pattern.affected_resource}
render phase: {pattern.render_phase}
code pattern: {pattern.code_pattern}
signal: {pattern.applicable_signal}

Canonical cluster:
name: {aggregate.canonical_name}
aliases: {aggregate.aliases}
examples: {json.dumps(examples[:3])}
"""
        try:
            return bool(complete_json(system, user, backend=backend, model=model, timeout=timeout).get("same_technique"))
        except LLMError as exc:
            print(f"    borderline merge judge failed: {exc}; keeping techniques separate")
            return False

    return judge


def aggregate_patterns(
    patterns: list[ExtractedPattern],
    prior: list[TechniqueAggregate] | None = None,
    judge: BorderlineJudge | None = None,
    auto_merge_threshold: float = 0.78,
    borderline_threshold: float = 0.35,
    min_observations: int = 3,
    min_repos: int = 2,
    min_consistency: float = 0.7,
) -> list[TechniqueAggregate]:
    """Aggregate deduplicated PR observations into stable canonical clusters."""
    prior = prior or []
    aggregates = [
        TechniqueAggregate(
            canonical_id=item.canonical_id,
            canonical_name=item.canonical_name,
            parent_strategy=item.parent_strategy,
            status=item.status,
            aliases=sorted(set(item.aliases + [normalize_technique(item.canonical_name)])),
            signature_aliases=item.signature_aliases,
        )
        for item in prior if item.parent_strategy in PARENT_STRATEGIES
    ]
    alias_lookup: dict[tuple[str, str], int] = {}
    token_index: dict[tuple[str, str], set[int]] = {}
    for index, item in enumerate(aggregates):
        for alias in item.aliases:
            alias_lookup[(item.parent_strategy, alias)] = index
        for match_text in _aggregate_match_texts(item):
            for token in _tokens(match_text):
                token_index.setdefault((item.parent_strategy, token), set()).add(index)
    seen_sources = set()
    for pattern in sorted(patterns, key=lambda item: item.source_id):
        if pattern.technique.strip().lower() in {"null", "none", "n/a"}:
            continue
        if pattern.source_id in seen_sources:
            continue
        seen_sources.add(pattern.source_id)
        if pattern.parent_strategy not in PARENT_STRATEGIES:
            continue
        normalized = normalize_technique(pattern.sub_strategy or pattern.technique)
        technique_alias = normalize_technique(pattern.technique)
        proposed_aliases = {
            normalize_technique(alias) for alias in pattern.sub_strategy_aliases if alias.strip()
        }
        pattern_match_text = _match_text(pattern)
        parent = pattern.parent_strategy
        target_index = alias_lookup.get((parent, normalized))
        target = aggregates[target_index] if target_index is not None else None
        candidate_indexes = set().union(
            *(token_index.get((parent, token), set()) for token in _tokens(pattern_match_text))
        ) if _tokens(pattern_match_text) else set()
        if target is None and candidate_indexes:
            scored = [
                (
                    max(
                        [lexical_similarity(pattern_match_text, text) for text in _aggregate_match_texts(item)]
                    ),
                    index,
                )
                for index in candidate_indexes
                for item in [aggregates[index]]
            ]
            score, best_index = max(scored, key=lambda pair: pair[0])
            best = aggregates[best_index]
            if score >= auto_merge_threshold:
                target = best
                target_index = best_index
            elif score >= borderline_threshold and judge is not None and judge(pattern, best):
                target = best
                target_index = best_index

        if target is None:
            canonical_id = f"{parent}--{_slug(pattern.sub_strategy or pattern.technique)}"
            used = {item.canonical_id for item in aggregates}
            if canonical_id in used:
                suffix = hashlib.sha1(f"{parent}:{normalized}".encode()).hexdigest()[:8]
                canonical_id = f"{canonical_id}-{suffix}"
            target = TechniqueAggregate(
                canonical_id=canonical_id,
                canonical_name=(pattern.sub_strategy or pattern.technique).strip(),
                parent_strategy=parent,
                aliases=sorted({normalized, technique_alias, *proposed_aliases}),
            )
            aggregates.append(target)
            target_index = len(aggregates) - 1
        else:
            target.aliases.extend([normalized, technique_alias, *proposed_aliases])

        for alias in (normalized, technique_alias, *proposed_aliases):
            alias_lookup[(parent, alias)] = target_index
            for token in _tokens(alias):
                token_index.setdefault((parent, token), set()).add(target_index)

        _add_observation(target, pattern)
        for token in _tokens(pattern_match_text):
            token_index.setdefault((parent, token), set()).add(target_index)

    populated = [item for item in aggregates if item.observation_count]
    for item in populated:
        item.aliases = sorted(set(item.aliases))
        item.signature_aliases = sorted(set(item.signature_aliases))[:20]
        item.repo_counts = dict(sorted(item.repo_counts.items()))
        item.framework_counts = dict(Counter(item.framework_counts).most_common())
        item.signal_counts = dict(Counter(item.signal_counts).most_common())
        item.metric_counts = dict(Counter(item.metric_counts).most_common())
        item.finalize(min_observations, min_repos, min_consistency)
        if hasattr(item, "_effect_items_by_metric"):
            del item._effect_items_by_metric
    return sorted(populated, key=lambda item: (-item.observation_count, item.canonical_id))


def to_technique_cluster(aggregate: TechniqueAggregate) -> TechniqueCluster | None:
    if not aggregate.eligible or not aggregate.representative_improvements:
        return None
    reps = aggregate.representative_improvements
    return TechniqueCluster(
        technique=aggregate.canonical_name,
        normalized_key=aggregate.canonical_id,
        frequency=aggregate.observation_count,
        avg_delta=aggregate.median_abs_delta,
        framework_hints=list(aggregate.framework_counts),
        applicable_signals=list(aggregate.signal_counts)[:10],
        why_it_works=reps[0]["why_it_works"],
        example_code_patterns=[item["code_pattern"] for item in reps],
        example_problem_symptoms=[item["problem_symptom"] for item in reps],
        source_pr_ids=[item["source_id"] for item in reps],
        distinct_repo_count=aggregate.distinct_repo_count,
        positive_count=aggregate.positive_count,
        negative_count=aggregate.negative_count,
        delta_p25=aggregate.delta_p25,
        delta_p75=aggregate.delta_p75,
        directional_consistency=aggregate.directional_consistency,
        confidence=aggregate.confidence,
        aliases=aggregate.aliases,
        parent_strategy=aggregate.parent_strategy,
        cwv_metrics=list(aggregate.metric_counts),
    )


def read_aggregates(path: Path) -> list[TechniqueAggregate]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        payload.pop("distinct_repo_count", None)
        items.append(TechniqueAggregate(**payload))
    return items


def write_aggregates(items: list[TechniqueAggregate], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            payload = asdict(item)
            payload["distinct_repo_count"] = item.distinct_repo_count
            handle.write(json.dumps(payload) + "\n")
