---
issue_type: cache-and-data-reuse
risk_tier: medium
source_prs: [Marcelo-Rosas/cargo-flow-navigator#90, NtFelix/RMS#1294, bigcommerce/catalyst#3013, NtFelix/RMS#1296]
---
# Cache and data reuse for context-specific and authenticated navigations

## What this addresses
This technique reduces unnecessary fetches and repeated lookups by reusing data only where it is safe to do so, while avoiding shared-cache reuse for user-specific navigations.

The evidence shows three related reuse patterns:
- splitting a generic vehicle-types hook into context-specific hooks so each screen requests only what it needs
- restoring cache validators on framework data responses so cached JSON can be validated and reused
- reusing request-scoped authenticated user data and customer access tokens so navigations do not repeat origin lookups or serve stale shared-cache results

## Evidence
- In `Marcelo-Rosas/cargo-flow-navigator#90`, the PR explicitly says the hook was split into semantic exports “to avoid over-fetch in contexts differentes,” and the call sites were updated to use context-specific hooks such as `useVehicleTypesOperational`, `useVehicleTypesAdmin`, and `useVehicleTypesFleetForm`.
- In `NtFelix/RMS#1294`, the release notes for the dependency bump call out “restore Content-Length and ETag for /_next/data/ JSON responses,” which supports browser/intermediary validation and reuse of framework data responses.
- In `bigcommerce/catalyst#3013`, authenticated route resolution now threads `customerAccessToken` through route and webpage queries, and authenticated requests bypass the shared KV route cache because it “is shared across customers and isn’t namespaced by identity.”
- In the same PR, webpage data switches to `fetchOptions: { cache: 'no-store' }` when a customer token is present, with the PR body stating this prevents a logged-in customer response from being served from the shared fetch cache to anonymous visitors or vice versa.
- In `NtFelix/RMS#1296`, `getAuthenticatedUser()` first reads a signed user object from request headers to “eliminate duplicate roundtrips to the Supabase API on page navigations,” and only falls back to `supabase.auth.getUser()` if the cached user data is unavailable or invalid.

## Recommended approach
- Split broad data hooks into context-specific entry points when different screens need different subsets of the same data.
- Preserve cache validators on framework-generated data responses when the response is safe to validate and reuse.
- For authenticated navigations, resolve user- or customer-specific data from the current request context rather than a shared cache that is not namespaced by identity.
- Reuse request-scoped authenticated user data when it is already available and verified, and fall back to origin lookup only when needed.
- Use uncached fetches for user-specific responses when shared caching could expose the wrong content across identities.

## Risks and limitations
- Context-specific hooks can increase the number of exported entry points and require careful call-site selection.
- Reusing request-scoped authenticated data depends on correct verification and trustworthy request propagation.
- Bypassing shared caches for authenticated requests can reduce cache hit rates, but it avoids cross-user leakage and stale responses.
- Restoring cache validators helps reuse, but only when the underlying response is safe to cache and validate.

## Anti-pattern evidence
Regression-side evidence was not supplied for this cluster.