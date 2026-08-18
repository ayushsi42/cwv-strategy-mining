---
issue_type: reuse-cache-and-data
risk_tier: medium
source_prs: [SimonOsipov/learn-greek-easy#567, bigcommerce/catalyst#3013, NtFelix/RMS#1296]
---
# Reuse persisted or authenticated data first, then revalidate in the background

## What this addresses
This pattern reduces critical-path latency by rendering from data that is already available locally or from authenticated request context, instead of blocking on a fresh network roundtrip.

The source changes show two related uses:
- a persisted session is reused synchronously so protected routes can render immediately, while auth revalidation runs afterward
- authenticated customer context is threaded into route and page-data resolution, while shared caches are bypassed or isolated to preserve correctness
- middleware-injected user data is reused to avoid duplicate user-fetch roundtrips on server-side requests

## Evidence
- In `SimonOsipov/learn-greek-easy#567`, the PR body says the app uses a “stale-while-revalidate auth bootstrap” to eliminate an LCP penalty caused by blocking on `GET /auth/me`, and that the store “already persists the session to `localStorage`.” The patch changes `RouteGuard` to initialize from `selectHasPersistedSession(useAuthStore.getState())` so it can render immediately, then run `checkAuth` in the background.
- In `bigcommerce/catalyst#3013`, authenticated route resolution is wrapped in `auth()`, and `req.auth?.user?.customerAccessToken` is passed into `getRoute` and `getRawWebPageContent`. The PR explicitly says authenticated requests bypass the shared KV route cache because it is not namespaced by customer identity, and webpage queries switch to `{ cache: 'no-store' }` when a customer token is present.
- In `NtFelix/RMS#1296`, middleware injects signed user data into headers, and server-side helpers read that header first in `getAuthenticatedUser(...)` to “eliminate duplicate roundtrips to the Supabase API on page navigations,” falling back to `supabase.auth.getUser()` only if the header is unavailable or invalid.

## Recommended approach
- Prefer already-persisted or already-available session/user context for the first render path.
- Trigger network revalidation after the optimistic render rather than before it.
- When request data depends on authenticated identity, pass that identity through the route/data lookup path.
- Keep shared caches from mixing authenticated and anonymous results; bypass or isolate cache usage when identity changes the response.
- Fall back to the network only when the local or injected data is missing or cannot be trusted.

## Risks and limitations
- Reusing persisted or injected data can show stale information briefly until revalidation completes.
- Identity-aware data reuse must preserve cache isolation; otherwise, one user’s response can be served to another.
- The source evidence shows correctness guards such as eviction on failed revalidation and cache bypass for authenticated requests, but the exact failure modes depend on the implementation.
- Regression-side evidence was not found in the supplied PRs.

## Anti-pattern evidence
No matched regression PR evidence was found.