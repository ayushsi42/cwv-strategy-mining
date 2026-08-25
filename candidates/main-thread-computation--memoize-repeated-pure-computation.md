---
issue_type: main-thread-computation--memoize-repeated-pure-computation
parent_strategy: main-thread-computation
risk_tier: low
cwv_metrics: []
source_prs: [reown-com/appkit#5292, commontoolsinc/labs#3899, WordPress/gutenberg#72796]
required_validation:
  - repeated_pure_computation_identified
  - cache_invalidation_on_write_present
  - cache_key_is_stable_per_read_variant
  - non_cacheable_path_falls_back_to_recompute
forbidden_techniques: []
---

# Memoize repeated pure computation

> **Risk tier:** low · **Parent strategy:** main-thread-computation · **CWV metric:** none supplied

## What this addresses

This strategy applies when the same pure or effectively pure computation is repeated on the main thread within a bounded scope, and the repeated work can be reused safely until an invalidating event occurs.

The evidence supports three concrete mechanisms:

- **Shared parsing helpers** to avoid repeating string handling and matching logic in origin checks.
- **Per-transaction read-result memoization** so repeated reads of the same cell in one ready transaction can reuse the prior result until any write invalidates the cache.
- **Memoized ramp generation** so repeated theme color ramp calculations reuse prior results for the same inputs.

The common shape is:

1. identify a repeated computation with stable inputs,
2. cache the result in a scope that matches the invalidation boundary,
3. bypass the cache when the scope is no longer safe.

## When to apply / when to skip

**Apply when:**
- the same computation is repeated with the same inputs in a short-lived scope;
- the result depends only on inputs already available at the call site;
- there is a clear invalidation event, such as a write or a changed input tuple;
- the cached path can be bypassed for special modes that must recompute.

**Skip when:**
- the computation is not demonstrably repeated;
- the result depends on hidden mutable state that is not invalidated by the cache boundary;
- the optimization would change semantics rather than reuse an equivalent result;
- the only evidence is correctness cleanup without a repeated-work pattern.

## Required validation

### `repeated_pure_computation_identified`

Observed evidence must show a repeated computation that is safe to reuse within a bounded scope.

Supported observations:
- `reown-com/appkit#5292` extracted URL/origin parsing into helpers such as `parseUrl`, `parseSchemelessHostPort`, `parseOriginRaw`, `matchNonWildcardPattern`, and `matchWildcardPattern`, replacing repeated inline string handling in origin matching.
- `commontoolsinc/labs#3899` added per-transaction caching for `Cell.get()` results because repeated reads in one ready transaction recomputed the same value, reactive reads, and CFC state.
- `WordPress/gutenberg#72796` memoized `buildBgRamp` and `buildAccentRamp` with `memize` because the same ramp generation was being repeated for identical seeds and background ramps.

### `cache_invalidation_on_write_present`

Observed evidence must show that the cache is explicitly invalidated when the invalidating event occurs.

Supported observations:
- `commontoolsinc/labs#3899` clears the whole read-result cache on any write by replacing the `WeakMap`, and also invalidates before write-after-prepare paths.
- `reown-com/appkit#5292` does not show a runtime cache invalidation mechanism; this validation is not applicable to that PR.
- `WordPress/gutenberg#72796` does not show invalidation logic in the patch; the memoization is bounded by input identity and max size rather than explicit write invalidation.

### `cache_key_is_stable_per_read_variant`

Observed evidence must show that the cache key is stable for the scope and distinguishes meaningful variants.

Supported observations:
- `commontoolsinc/labs#3899` keys cached reads by the cell’s stable link identity plus a `variant` string derived from read options.
- `WordPress/gutenberg#72796` memoizes by function arguments: seed for `buildBgRamp`, and seed plus background ramp for `buildAccentRamp`.
- `reown-com/appkit#5292` does not introduce memoization keys; it introduces parsing and matching helpers instead.

### `non_cacheable_path_falls_back_to_recompute`

Observed evidence must show a path that intentionally bypasses caching when caching is not safe.

Supported observations:
- `commontoolsinc/labs#3899` leaves cache methods undefined for the non-reactive `sample()` wrapper, so callers fall back to recomputation.
- `commontoolsinc/labs#3899` also bypasses the cache once CFC is prepared so the real read path still runs and invalidation is preserved.
- `WordPress/gutenberg#72796` does not show a separate non-cacheable mode in the patch.
- `reown-com/appkit#5292` does not show caching, so this validation is not applicable there.

## Recommended approaches

Prefer the smallest cache boundary that matches the invalidation boundary.

### Good

```ts
const getCachedBgRamp = memoize(buildBgRamp, { maxSize: 10 })
const getCachedAccentRamp = memoize(buildAccentRamp, { maxSize: 10 })

const bgRamp = getCachedBgRamp(seeds.bg)
computedColorRamps.set(rampName, getCachedAccentRamp(seed, bgRamp))
```

This is supported by `WordPress/gutenberg#72796`: the repeated work is the ramp generation itself, and the cache key is the function input tuple.

### Good

```ts
const cacheable =
  tx !== undefined &&
  tx.getCachedReadResult !== undefined &&
  tx.status().status === 'ready' &&
  tx.getCfcState().prepare.status !== 'prepared'

if (cacheable) {
  const cached = tx.getCachedReadResult(this._link, variant)
  if (cached !== undefined) return cached.value
}
```

This is supported by `commontoolsinc/labs#3899`: cache only when the transaction is in the safe state, and bypass when a later phase requires the real read path.

### Good

```ts
export function parseOriginRaw(origin: string): { scheme: string; host: string; port?: string } | null {
  const schemeIdx = origin.indexOf('://')
  if (schemeIdx === -1) return null
  // parse once, reuse in matching helpers
}
```

This is supported by `reown-com/appkit#5292`: repeated origin parsing was factored into reusable helpers to avoid duplicating string handling across matching paths.

## Anti-patterns

The evidence is insufficient to support a concrete bad-pattern example for this child strategy. The supplied PRs show positive refactors and cache insertion, but they do not provide a defensible pre-change regression patch that can be generalized into a safe “Bad” example.

## How to verify

Use the same measurements and assertions already present in the evidence:

- For repeated-read caching, verify that a second read in the same ready transaction returns the same cached result object, and that a write causes the next read to recompute.
- For memoized ramp generation, verify that the same seed/background inputs reuse the cached ramp result, while different inputs still produce the expected distinct result.
- For origin matching helpers, verify that the helper-based path preserves the same allow/deny outcomes for the covered pattern classes.

Do not promise a fixed CWV improvement from this strategy alone. The supplied evidence does not include before/after CWV metrics.

## Evidence and confidence

### Observed facts
- `reown-com/appkit#5292` introduced reusable URL/origin parsing helpers and pattern matchers for origin checks, including explicit handling for schemeless host:port patterns, wildcard labels, and raw host comparison.
- `commontoolsinc/labs#3899` added per-transaction memoization for `Cell.get()` results, keyed by stable cell identity and read variant, with invalidation on writes and bypass for non-cacheable paths.
- `WordPress/gutenberg#72796` memoized repeated color-ramp generation with `memize`, using cached wrappers for `buildBgRamp` and `buildAccentRamp`.

### Inference
- These changes all fit the same child strategy: repeated pure computation on the main thread can be reused when the cache boundary matches the invalidation boundary.
- The strategy is low risk because the evidence emphasizes bounded reuse, explicit invalidation, and fallback paths rather than speculative broad caching.

### Confidence
- **Medium**: three observations across three repositories, with directional consistency reported as 100% and no regressions in the supplied evidence.