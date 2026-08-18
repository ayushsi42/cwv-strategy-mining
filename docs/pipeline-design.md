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
2. **Extract:** derive a technique, symptom, code pattern, explanation,
   framework hint, and audit signal from each real PR and patch.
3. **Aggregate:** assign observations to persistent canonical technique IDs.
   Exact aliases resolve deterministically, high lexical similarity merges
   automatically, and only borderline pairs use an LLM equivalence judge.
   The registry stores observation/repository counts, direction consistency,
   per-metric effect distributions, aliases, and bounded representative PRs.
   A technique advances only with at least three observations, two independent
   repositories, and 70% improvement-side consistency by default.
4. **Classify:** keep reusable delivered-page CWV techniques; drop incidental
   correlations, unrelated build-time work, vague refactors, and duplicates.
   Classification is platform-neutral.
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

- Borderline semantic assignment still depends on an LLM judgment, but each
  accepted alias is persisted so future runs resolve it deterministically.
- Bot templates without a verified live example never claim a measured signal.
- Front-end and CI/docs filtering uses filename heuristics.
- Generation validation checks structure and provenance fields; factual review
  of prose remains a human step.
- No Checks API channel is scanned, so tools reporting only through checks are
  not discovered.
