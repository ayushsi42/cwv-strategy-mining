"""Stage 1: turn a PR's bot comments into a signal_type label. New relative to
smol-planner (their signal_type came pre-labeled from a third-party HF
dataset) -- this derives it from free GH Archive comment bodies.

Two metric shapes, handled differently:
  - "point-in-time" metrics (a Lighthouse performance score, raw LCP/CLS/...
    ms values): meaningless alone, need first-vs-last across >=2 Tier-A
    comments on the same PR to get a real delta.
  - "already-a-delta" metrics (RelativeCI / bundle-size-table's reported
    percentage change): the single comment already IS a before/after
    comparison, so one Tier-A comment suffices.

Mirrors smol-planner's cwv_pattern_mining.py `--min-perf-delta 5.0` default
for the performance-score threshold, for consistency with an established
convention rather than picking an arbitrary new number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cwv_playbook_miner.labeling.registry import match_template
from cwv_playbook_miner.sourcing.gharchive_mine import CommentHit

HIGHER_IS_BETTER = {
    "performance": True,
    "lcp_ms": False,
    "cls": False,
    "fcp_ms": False,
    "tbt_ms": False,
    "si_ms": False,
    "bundle_size_delta_pct": False,
}
ALREADY_DELTA_METRICS = {"bundle_size_delta_pct"}

DEFAULT_THRESHOLDS = {
    "performance": 5.0,           # points, matches smol-planner's cwv_pattern_mining.py default
    "lcp_ms": 100.0,
    "cls": 0.02,
    "fcp_ms": 100.0,
    "tbt_ms": 50.0,
    "si_ms": 200.0,
    "bundle_size_delta_pct": 1.0,  # percent
}


@dataclass
class LabeledPR:
    repo: str
    pr_number: int
    signal_type: str  # perf_improvement | perf_decrease | neutral | unlabeled
    tier: str          # A | B | none
    metric_key: str | None = None
    before: float | None = None
    after: float | None = None
    delta: float | None = None
    n_comments_seen: int = 0
    n_tier_a_comments: int = 0
    template_names: list[str] = field(default_factory=list)


def _classify_delta(metric_key: str, delta: float, thresholds: dict) -> str:
    threshold = thresholds.get(metric_key, DEFAULT_THRESHOLDS.get(metric_key, 0.0))
    higher_is_better = HIGHER_IS_BETTER.get(metric_key, True)
    signed_delta = delta if higher_is_better else -delta
    if signed_delta >= threshold:
        return "perf_improvement"
    if signed_delta <= -threshold:
        return "perf_decrease"
    return "neutral"


def label_pr(repo: str, pr_number: int, comments: list[CommentHit], thresholds: dict | None = None) -> LabeledPR:
    thresholds = thresholds or DEFAULT_THRESHOLDS
    comments_sorted = sorted(comments, key=lambda c: c.created_at)

    parsed: list[tuple[CommentHit, dict, str]] = []  # (comment, metrics, template_name)
    for c in comments_sorted:
        template = match_template(c.actor, c.body)
        metrics = template.parse(c.body) if template else None
        if metrics:
            parsed.append((c, metrics, template.NAME))

    template_names = sorted({name for _, _, name in parsed}) or sorted(
        {match_template(c.actor, c.body).NAME for c in comments_sorted}
    )

    if not parsed:
        return LabeledPR(
            repo=repo, pr_number=pr_number, signal_type="unlabeled", tier="B",
            n_comments_seen=len(comments_sorted), n_tier_a_comments=0,
            template_names=template_names,
        )

    # Already-a-delta metrics: one Tier-A comment is enough. Use the latest.
    for metric_key in ALREADY_DELTA_METRICS:
        hits = [(c, m[metric_key]) for c, m, _ in parsed if metric_key in m]
        if hits:
            _, value = hits[-1]
            return LabeledPR(
                repo=repo, pr_number=pr_number,
                signal_type=_classify_delta(metric_key, value, thresholds), tier="A",
                metric_key=metric_key, before=None, after=None, delta=value,
                n_comments_seen=len(comments_sorted), n_tier_a_comments=len(parsed),
                template_names=template_names,
            )

    # Point-in-time metrics: need first vs last sharing a common key.
    all_keys = {k for _, m, _ in parsed for k in m}
    for metric_key in all_keys:
        hits = [(c, m[metric_key]) for c, m, _ in parsed if metric_key in m]
        if len(hits) < 2:
            continue
        before = hits[0][1]
        after = hits[-1][1]
        return LabeledPR(
            repo=repo, pr_number=pr_number,
            signal_type=_classify_delta(metric_key, after - before, thresholds), tier="A",
            metric_key=metric_key, before=before, after=after, delta=after - before,
            n_comments_seen=len(comments_sorted), n_tier_a_comments=len(parsed),
            template_names=template_names,
        )

    # Exactly one Tier-A comment, no second data point yet -- not guessed at.
    return LabeledPR(
        repo=repo, pr_number=pr_number, signal_type="unlabeled", tier="A",
        n_comments_seen=len(comments_sorted), n_tier_a_comments=len(parsed),
        template_names=template_names,
    )


def label_scan_result(comment_hits: list[CommentHit], thresholds: dict | None = None) -> list[LabeledPR]:
    by_pr: dict[tuple[str, int], list[CommentHit]] = {}
    for c in comment_hits:
        by_pr.setdefault((c.repo, c.pr_number), []).append(c)
    return [label_pr(repo, pr_number, comments, thresholds) for (repo, pr_number), comments in by_pr.items()]
