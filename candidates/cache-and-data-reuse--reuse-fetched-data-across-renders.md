---
issue_type: cache-and-data-reuse--reuse-fetched-data-across-renders
parent_strategy: cache-and-data-reuse
risk_tier: low
cwv_metrics:
  - bundle_size_delta_pct
  - Lighthouse network requests / repeat-load latency
  - Lighthouse repeated network requests / API latency
source_prs:
  - ant-design/ant-design#55186
  - woowacourse/perf-basecamp#183
  - woowacourse/perf-basecamp#170
required_validation:
  - repeated_request_has_stable_cache_key
  - cached_result_is_reused_for_subsequent_consumers
  - cache_scope_matches_expected_lifetime
forbidden_techniques: []
# Reuse fetched data across renders

> **Risk tier:** low · **Parent strategy:** cache-and-data-reuse · **Measured metric:** `bundle_size_delta_pct`

## What this addresses

This strategy reduces repeated work when the same fetched data is needed more than once across renders or consumers.

The evidence supports these mechanisms:
- cache a request result behind a stable key and return the same promise/result to later callers
- reuse fetched API data from session-scoped storage for repeated requests
- reuse a previously fetched response for a fixed API URL
- replace ad hoc fetch-on-mount patterns with a shared data-fetching layer that can reuse in-flight or completed requests

Supported effect from the evidence:
- reduced repeated network transfer and repeated client-side work for identical data fetches

## When to apply / when to skip

### Apply when
- the same request is issued from multiple renders, components, or consumers
- the request key is stable enough to identify identical data
- the data can be safely reused within the intended cache lifetime
- the code currently fetches the same resource in multiple places or on repeated visits

### Skip when
- the response is highly user-specific, rapidly changing, or unsafe to reuse across consumers
- the request key cannot be made stable and precise
- the code path depends on always-fresh data and no cache invalidation plan exists
- the fetch is already handled by an equivalent shared cache layer and no duplicate work remains

## Required validation

### `repeated_request_has_stable_cache_key`
Validate that identical requests map to the same cache key.

What to check:
- a fixed string key for a fixed resource, or
- a deterministic key derived from request identity
- the same key is used on subsequent calls for the same data source

Evidence:
- `ant-design/ant-design#55186` uses `key: \`component-changelog-${lang}\`` for the changelog import cache.
- `woowacourse/perf-basecamp#183` uses `TRENDING_CACHE_KEY = 'trending_gifs'` for the trending GIF response.
- `woowacourse/perf-basecamp#170` uses the full request URL string as the cache lookup key for the trending API response.

### `cached_result_is_reused_for_subsequent_consumers`
Validate that the second and later consumers receive the cached promise/result instead of issuing a new fetch.

What to check:
- a cache lookup occurs before the request is created, and
- the cached value is returned directly when present, or
- a cached response is read before performing a network request

Evidence:
- `ant-design/ant-design#55186` returns the cached promise from `cache.promise(...)` when present.
- `woowacourse/perf-basecamp#183` returns `cachedData` immediately when `sessionCache.get(...)` succeeds.
- `woowacourse/perf-basecamp#170` checks `cacheStorage.match(...)` before calling `fetch(...)`.

### `cache_scope_matches_expected_lifetime`
Validate that the cache lifetime matches the reuse intent.

What to check:
- in-memory promise reuse for repeated consumers during the same runtime, or
- session-scoped storage for reuse within the session, or
- persistent response reuse only where the code explicitly stores and retrieves the response

Evidence:
- `ant-design/ant-design#55186` uses a module-level in-memory cache.
- `woowacourse/perf-basecamp#183` uses `sessionCache`, indicating session-scoped reuse.
- `woowacourse/perf-basecamp#170` uses the Cache Storage API with `caches.open(...)` and `cache.put(...)`.

## Recommended approaches

### Shared promise cache for repeated requests

Use a stable key and return the same promise for identical requests.

Good:
```ts
class FetchCache {
  private cache: Map<string, PromiseLike<any>> = new Map();

  promise<T>(key: string, promiseFn: () => PromiseLike<T>): PromiseLike<T> {
    const cached = this.cache.get(key);
    if (cached) {
      return cached;
    }
    const promise = promiseFn();
    this.cache.set(key, promise);
    return promise;
  }
}
```

Why this is valid:
- The key is stable.
- The first caller creates the request.
- Later callers reuse the same promise.

### Session-scoped response reuse

If the data should be reused during the session, read from session cache before fetching.

Good:
```ts
const cachedData = sessionCache.get<GifImageModel[]>(TRENDING_CACHE_KEY);

if (cachedData) {
  return cachedData;
}

const gifs = await fetchGifs(url);
sessionCache.set(TRENDING_CACHE_KEY, gifs);

return gifs;
```

Why this is valid:
- The cache is checked before the fetch.
- The result is reused on subsequent calls.
- The cache lifetime matches session reuse.

### Response reuse for a fixed request URL

If the request is a fixed URL and the response can be reused, check cache storage before network fetch.

Good:
```ts
const cacheStorage = await caches.open('trending');
const cachedResponse = await cacheStorage.match(TRENDING_GIF_API);

if (cachedResponse) {
  const gifs: GifsResult = await cachedResponse.json();
  return convertResponseToModel(gifs.data);
}

const response = await fetch(TRENDING_GIF_API);

if (response.ok) {
  await cacheStorage.put(TRENDING_GIF_API, response.clone());
  const gifs: GifsResult = await response.json();
  return convertResponseToModel(gifs.data);
}
```

Why this is valid:
- The cache key is the full request URL.
- The cached response is used before network fetch.
- The response is stored for later reuse.

## Evidence-derived examples

### Good: stable key with shared promise reuse
From `ant-design/ant-design#55186`, the cache helper returns the same promise for the same key:
- `cache.promise<T>(key, request)` checks the cache first
- `key` is derived from the request identity
- repeated consumers share the same in-flight or completed result

### Good: session-scoped reuse before fetch
From `woowacourse/perf-basecamp#183`, trending GIF data is reused from session cache:
- `sessionCache.get<TRENDING_CACHE_KEY>()` is checked first
- the network request runs only on cache miss
- the fetched result is stored back into session cache

### Good: response reuse for a fixed URL
From `woowacourse/perf-basecamp#170`, the trending API response is reused through Cache Storage:
- `cacheStorage.match(TRENDING_GIF_API)` is checked first
- `fetch(TRENDING_GIF_API)` runs only on cache miss
- the response is cloned and stored for later reuse

## Anti-patterns

No evidence-backed anti-pattern regex is provided.

## How to verify

Use the supplied metrics and compare before/after behavior for the same route or interaction.

### `bundle_size_delta_pct`
Measure the change in bundle-size-related delta associated with repeated fetch handling or duplicated request logic.

Verification:
- record the metric before the change
- record the metric after the change
- confirm the delta direction matches the intended reduction in repeated work

### Lighthouse network requests / repeat-load latency
Measure whether repeated loads issue fewer duplicate requests and complete faster.

Verification:
- run the same navigation or repeat-load scenario before and after the change
- compare the number of repeated network requests
- compare repeat-load latency

### Lighthouse repeated network requests / API latency
Measure whether repeated API fetches are avoided or served faster from cache.

Verification:
- run the same API-consuming flow twice in the same session or runtime
- compare repeated request counts
- compare API latency on the second pass

## Evidence and confidence

Observed facts:
- `ant-design/ant-design#55186` removed a custom fetch cache helper and replaced ad hoc fetch usage with `useSWR`, while also using SWR for site data and changelog data. The patch shows stable keys and shared reuse of fetched results.
- `woowacourse/perf-basecamp#183` added `sessionCache` reuse for trending GIF data and returned cached data before fetching.
- `woowacourse/perf-basecamp#170` added Cache Storage-based reuse for a fixed trending API URL and returned cached JSON from storage before fetch.
- The strategy summary reports 3 observations across 2 repositories, 100% directional consistency, and a median `bundle_size_delta_pct` delta of 67.83.

Inference:
- Reusing fetched data across renders can reduce repeated network transfers and repeated client work when the same data is requested multiple times.
- The safest implementation shape is a stable request key plus a cache lookup before fetch, with cache lifetime aligned to the reuse requirement.

## Risks and limitations

- Cache correctness matters: stale or user-specific data can be reused incorrectly if the key or lifetime is too broad.
- A cache only helps when the same request is actually repeated; otherwise it adds complexity without measurable benefit.
- Different cache scopes have different tradeoffs: in-memory, session-scoped, and response storage are not interchangeable.
- The evidence supports reuse patterns, but not a universal recommendation to cache every fetch.