---
issue_type: cache-and-data-reuse--request-scoped-authenticated-data-reuse
parent_strategy: cache-and-data-reuse
risk_tier: medium
cwv_metrics: [performance]
source_prs: [NtFelix/RMS#1294, bigcommerce/catalyst#3013, NtFelix/RMS#1296]
required_validation:
  - authenticated_request_detected
  - request_scoped_user_identity_available
  - cached_data_request_uses_identity_specific_fetch_mode
forbidden_techniques: []
---

# Request-scoped authenticated data reuse

> **Risk tier:** medium · **Parent strategy:** cache-and-data-reuse · **CWV metric:** performance

## Summary

Use this strategy when a navigation or framework data request depends on authenticated user state, but the request can still benefit from correct cache validation, identity threading, or request-scoped reuse.

The evidence supports two distinct mechanisms:

1. **Framework data validator restoration**  
   A Next.js backport restored `Content-Length` and `ETag` for `/_next/data/` JSON responses. The measured PR associated with that change showed a performance improvement.

2. **Authenticated request-scoped data reuse**  
   Customer-specific route resolution and webpage queries were fixed by threading the customer access token through route resolution and page data fetches. Authenticated requests bypassed a shared route cache, and authenticated webpage fetches switched to `cache: 'no-store'` to prevent cross-identity reuse.

A third evidence thread shows a related but separate optimization: middleware can refresh session state and make verified user data available to server-side code to avoid duplicate auth fetches. That is request-scoped auth reuse, not framework data validator restoration.

## Apply / Skip

### Apply when
- The request is served in an authenticated context.
- Route resolution, navigation state, or page data depends on user/customer identity.
- The same endpoint serves both anonymous and authenticated traffic.
- You observe duplicate auth fetches, incorrect authenticated navigation, or a shared cache that is not namespaced by identity.
- The response is a framework data JSON or equivalent navigational payload that can benefit from preserved validators.

### Skip when
- The response is not identity-sensitive and can be shared normally.
- The data source already has correct cache semantics for authenticated requests.
- The route or data fetch is intentionally uncached for correctness and there is no evidence that validator restoration changes behavior.
- No request-scoped identity signal is available where the route or fetch is executed.

## Required validation

### `authenticated_request_detected`
Confirm that the request is actually operating under authenticated context.

What to verify:
- The request handler can read a user or customer token from request-scoped auth state.
- The authenticated branch is taken only when that token exists.
- In the Catalyst evidence, `req.auth?.user?.customerAccessToken` is the signal used to distinguish authenticated requests.

### `request_scoped_user_identity_available`
Confirm that the identity needed for the route or fetch is available at the point of use.

What to verify:
- The token or user identity is threaded into the route resolver and/or data fetcher.
- In the Catalyst evidence, `customerAccessToken` is passed into `getRoute`, `getRawWebPageContent`, and webpage data fetches.
- In the middleware/session evidence, verified user data is made available to server-side code through request headers after middleware processing.

### `cached_data_request_uses_identity_specific_fetch_mode`
Confirm that authenticated requests do not reuse a shared cache entry across identities.

What to verify:
- Authenticated requests either bypass the shared cache or use a fetch mode that prevents shared reuse.
- In the Catalyst evidence, authenticated webpage queries switch to `{ cache: 'no-store' }`.
- In the route proxy evidence, authenticated requests bypass the shared KV route cache because it is keyed only by pathname and channel, not customer identity.

## Recommended approaches

### 1) Restore validators on framework data JSON when the framework owns the data route

Use this when the framework-owned data endpoint is missing response validators and the fix is to restore them so the browser or intermediaries can validate and reuse the response.

Good:
```ts
return new Response(body, {
  headers: {
    'Content-Length': String(body.length),
    ETag: etag,
  },
});
```

This reflects the evidence from the Next.js backport that restored `Content-Length` and `ETag` for `/_next/data/` JSON responses.

### 2) Thread authenticated identity into route resolution and page data fetches

Use this when route resolution or page queries depend on customer or user identity.

Good:
```ts
const customerAccessToken = req.auth?.user?.customerAccessToken;

const route = await getRoute(pathname, channelId, customerAccessToken);
const page = await getWebPage(id, customerAccessToken);
```

This matches the Catalyst evidence: identity is read once from request-scoped auth state and passed through the route and data stack.

### 3) Disable shared caching for authenticated fetches that can vary by user

Use this when the same query can return different results for authenticated and anonymous traffic, or across different authenticated users.

Good:
```ts
const fetchOptions = customerAccessToken
  ? { cache: 'no-store' }
  : { next: { revalidate } };

await client.fetch({
  document: NormalPageQuery,
  variables,
  customerAccessToken,
  fetchOptions,
});
```

This is directly supported by the webpage data patch. The authenticated branch avoids shared cache reuse.

### 4) Bypass shared route caches when identity affects resolution

Use this when a route cache key is shared across users and is not identity-aware.

Good:
```ts
if (customerAccessToken) {
  return {
    route: await getRoute(pathname, channelId, customerAccessToken),
    status,
  };
}
```

The evidence explicitly states that the shared KV route cache was bypassed for authenticated requests because it was keyed only by pathname and channel, not customer identity.

## Bad examples

No evidence-backed anti-pattern was supplied with a pre-change regression or failing patch. Do not invent a universal forbidden regex or a generic bad pattern here.

## Verification

Use measurable checks tied to the observed behavior. Do not assume a fixed gain.

### For validator restoration on framework data JSON
- Measure the relevant performance metric before and after the change.
- Confirm that the data response includes the expected validators and length metadata.
- Verify that navigations using the framework data request no longer re-download the same JSON when validation is possible.

### For authenticated request-scoped reuse
- Measure performance before and after the change.
- Verify that authenticated navigation resolves the correct customer-specific route or page.
- Confirm that anonymous and authenticated requests do not share the same personalized response.
- Confirm that a customer-restricted page is visible and accessible only for the correct authenticated identity.
- Confirm that route resolution and page data fetches use the authenticated token when present.

Observed PRs reported performance deltas of +5, +6, and +9, with a median delta of +6. That is evidence, not a guarantee.

## Evidence

### Raw observations

#### NtFelix/RMS#1294
- **Title:** `chore(deps): bump next from 15.5.11 to 15.5.14`
- **Measured:** performance `42 -> 47` (`delta 5`)
- **Relevant release note:** `Fix(pages-router): restore Content-Length and ETag for /_next/data/ JSON responses`
- **Interpretation:** the PR associates validator restoration for framework data JSON with improved performance.

#### bigcommerce/catalyst#3013
- **Title:** `fix: TRAC-293 Pass customer token through routes and webpages`
- **Measured:** performance `68 -> 77` (`delta 9`)
- **Relevant changes:**
  - `customerAccessToken` threaded into route resolution and webpage queries
  - authenticated requests bypassed a shared KV route cache
  - authenticated webpage fetches switched to `cache: 'no-store'`
- **Interpretation:** the PR shows request-scoped identity threading and identity-aware cache scoping for authenticated navigation.

#### NtFelix/RMS#1296
- **Title:** `experiment(auth): test edge bundle footprint with session cookie refr…`
- **Measured:** performance `47 -> 53` (`delta 6`)
- **Relevant changes:**
  - middleware refreshed session state
  - verified user data was forwarded to server-side code through request headers
  - duplicate auth roundtrips were reduced
- **Interpretation:** the PR shows request-scoped authenticated user reuse to avoid repeated auth fetches.

### Evidence-derived facts
- Restoring `Content-Length` and `ETag` can improve reuse of framework data JSON when the response is otherwise cacheable.
- Authenticated route resolution must be identity-aware when the cache key is not namespaced by user.
- Authenticated data fetches that vary by user should not reuse a shared cache entry.
- Request-scoped auth reuse can reduce duplicate auth fetches, but it is a separate mechanism from shared response caching.

### Inference
- The correct cache-and-data-reuse response depends on whether the request is identity-sensitive and whether the cache key includes identity.
- Validator restoration is appropriate only when the framework or intermediary can act on the restored metadata.
- Identity threading and cache bypass are correctness measures for personalized navigation, not universal performance rules.

## Risks and limitations

- This strategy is only safe when the request-scoped identity is available and trustworthy at the point of fetch or route resolution.
- Shared caches that are not namespaced by identity can leak personalized content if reused for authenticated requests.
- Switching authenticated requests to `no-store` protects correctness but may reduce reuse; apply it only where the response can vary by user.
- Validator restoration helps only when the response is suitable for reuse and the framework or intermediary can use `Content-Length` and `ETag`.
- The evidence does not support a universal rule that all authenticated data should be uncached. The correct choice depends on whether the response is identity-specific and whether the cache key includes identity.

## Confidence

**Medium**

The evidence is consistent across three observations and two repositories, but the mechanisms are not identical. One mechanism is validator restoration for framework data JSON; the others are authenticated identity threading and cache scoping.