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
   derives the specific technique, broad controlled family, mechanism, resource,
   render phase, symptom, code pattern, explanation, framework, and audit signal.
   Up to eight compact PRs share one request. Per-record content-hash caching makes
   reruns independent of batch boundaries and avoids repeat calls.
3. **Aggregate:** merge observations locally by their controlled broad family,
   retaining specific changes as aliases and examples. Legacy observations without
   a family continue through deterministic exact/high-similarity matching, with an
   LLM judge only for borderline legacy pairs.
   The registry stores observation/repository counts, direction consistency,
   per-metric effect distributions, aliases, and bounded representative PRs.
   A technique advances only with at least three observations, two independent
   repositories, and 70% improvement-side consistency by default.
4. **Classify:** review only statistically eligible broad families for generic
   usefulness and risk. Raw PR content is not resent at this stage.
5. **Match regressions:** find extracted performance-decrease patterns matching
   each surviving cluster for independent anti-pattern evidence.
6. **Generate:** render a generic Markdown candidate from the raw source PR
   bodies and patches. The prompt forbids platform translation and invented
   implementation or anti-pattern details. When regression evidence is absent,
   the candidate must say so.

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
risk_tier: <low|medium|high>
source_prs: [<repo#number>, ...]
---
```

Required sections are `What this addresses`, `Evidence`, `Recommended approach`,
`Risks and limitations`, and `Anti-pattern evidence`.

## Current limitations

- Legacy records without a controlled family can require an LLM equivalence
  judgment; newly fused extraction records never require pairwise LLM merging.
- Bot templates without a verified live example never claim a measured signal.
- Front-end and CI/docs filtering uses filename heuristics.
- Generation validation checks structure and provenance fields; factual review
  of prose remains a human step.
- No Checks API channel is scanned, so tools reporting only through checks are
  not discovered.
