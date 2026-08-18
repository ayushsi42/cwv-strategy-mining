# CWV strategy-mining pipeline

This standalone pipeline discovers real merged PRs with measured web-performance
changes and turns them into platform-neutral, reviewable technique candidates.

## Funnel

```text
source + label -> extract -> cluster -> classify -> match regressions -> generate
```

1. **Source and label:** scan GH Archive bot comments and merged PR events,
   parse verified Lighthouse or bundle-report formats, calculate deltas, and
   fetch diffs only for labeled merged PRs. A larger external corpus supplies
   additional real improvement PRs when live-window yield is sparse.
2. **Extract:** one fused response rejects non-page-performance correlations and
   derives the specific technique, one of 15 stable parent strategies, a proposed
   reusable sub-strategy, mechanism, resource, render phase, symptom, code pattern,
   explanation, framework, and audit signal.
   Up to eight compact PRs share one request. Per-record content-hash caching makes
   reruns independent of batch boundaries and avoids repeat calls.
3. **Resolve and aggregate:** exact child aliases merge locally. Ambiguous proposed
   children are shortlisted only among siblings of the same parent and resolved in
   bounded LLM batches. Specific PR changes remain aliases/examples. One observation
   creates a provisional child; repetition across two repositories promotes it to an
   active child. Parents organize discovery; a child is the publication unit and
   advances only with at least three observations, two repositories, and 70%
   improvement consistency.
   Valid techniques outside all fixed parents are written to a proposal pool. Even a
   repeated proposal requires human review before the stable parent set changes.
   The registry stores observation/repository counts, direction consistency,
   per-metric effect distributions, aliases, and bounded representative PRs.
   A technique advances only with at least three observations, two independent
   repositories, and 70% improvement-side consistency by default.
4. **Classify:** review only statistically eligible child strategies for generic
   usefulness and risk. Raw PR content is not resent at this stage.
5. **Match regressions:** find extracted performance-decrease patterns matching
   each surviving cluster for independent anti-pattern evidence.
6. **Generate and critique:** draft an expert, platform-neutral child playbook from
   raw source bodies/patches, then run a second technical-editor pass. The revised
   output is written directly; deterministic validation is diagnostic only.

Every intermediate stage is JSONL under `data/processed/` and can be inspected
or rerun independently.

Long historical sweeps use `backfill`, which scans bounded 24-hour chunks,
confirms only sparse comment hits through the GitHub API, deduplicates records
into the existing source JSONL, and advances its cursor only after a chunk's
records have been written. An interrupted run therefore resumes without
silently skipping unpublished results.

## Candidate contract

```yaml
---
issue_type: <kebab-case slug>
parent_strategy: <one of 15 stable parent IDs>
risk_tier: <low|medium|high>
cwv_metrics: [<measured metric>, ...]
source_prs: [<repo#number>, ...]
required_validation: [<snake_case validation ID>, ...]
forbidden_techniques: []
---
```

Required sections cover Apply/Skip gates, validation, concrete recommended examples,
anti-patterns, verification, evidence/confidence, and risks/limitations.

## Current limitations

- Ambiguous sibling resolution still depends on an LLM, but requests are batched,
  parent-scoped, cached at extraction, and never allowed to invent a parent.
- Bot templates without a verified live example never claim a measured signal.
- Front-end and CI/docs filtering uses filename heuristics.
- The critic and deterministic contract substantially raise quality, but final
  factual approval remains a human responsibility.
- No Checks API channel is scanned, so tools reporting only through checks are
  not discovered.
