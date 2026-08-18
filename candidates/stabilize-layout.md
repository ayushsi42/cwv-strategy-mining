---
issue_type: stabilize-layout
risk_tier: low
source_prs: [lgtm-hq/turbo-themes#347, taverns-red/toast-stats#1202, taverns-red/toast-stats#590]
---
# Stabilize layout before late content or theme changes arrive

## What this addresses
This technique reserves or stabilizes the page slot before a later-arriving theme, panel, or lazy component would otherwise cause a visible shift.

Across the supplied PRs, the shared pattern is:

- apply the correct theme state before paint and remove stale theme CSS links after the new stylesheet is ready
- render a height-matched skeleton while a secondary query is still loading
- short-circuit a lazy wrapper when the wrapped component would render `null` anyway

In each case, the goal is the same: avoid a late insert, collapse, or theme flash that would move content and increase CLS.

## Evidence
### lgtm-hq/turbo-themes#347
The patch extracts and tests the inline theme-switching logic used for FOUC prevention, and it removes redundant theme CSS after the active theme stylesheet is loaded.

Supported excerpts:
- `Extracts the FOUC-prevention and inline theme-switching logic`
- `applyInitialTheme()`
- `needsCssUpdate()`
- `themeLink.href = new URL(href, windowObj.location.href).pathname`
- `existingLinks.forEach((link) => { ... if (linkThemeId !== theme.id && linkThemeId !== "base") { link.remove(); } })`

The same PR also sanitizes the base URL used for asset paths:
- `sanitizeBaseUrl(raw: string): string`
- rejects protocol-relative and absolute URLs

### taverns-red/toast-stats#1202
The PR explicitly describes a late-loading panel that returned `null` until data arrived, then expanded and pushed content downward.

Supported excerpts:
- `returned null until its data ... arrived, then expanded and shoved everything below it down`
- `when !status && isLoading it renders a height-matched skeleton instead of null`
- `DistrictDetailPage threads isLoading={isLoadingCompetitiveAwards} down`
- `the primary page content is not gated on the secondary query`

### taverns-red/toast-stats#590
The PR identifies a Suspense fallback reserving space for a component that would often render `null`, and fixes it by hoisting the null guard.

Supported excerpts:
- `Suspense fallback reserves a 400px chart-skeleton on every landing-page mount`
- `ComparisonPanel itself returns null when fewer than 2 districts are pinned`
- `if (props.pinnedDistricts.length < 2) return null`
- `No Suspense → no skeleton → no shift`

The PR also updates tests to await the lazy render path once the second district is pinned.

## Recommended approach
Use the smallest layout-stabilizing change that matches the actual late-arriving behavior:

1. If a theme or stylesheet choice is known before paint, apply it early and remove stale theme CSS after the correct stylesheet is in place.
2. If a secondary query resolves later than the main page content, render a height-matched skeleton or reserved slot while loading.
3. If a lazy wrapper would only render `null` for the default state, hoist that null guard into the wrapper so the fallback never appears unnecessarily.

Keep the reserved geometry aligned with the loaded shape where possible, and let the real content fill the slot in place.

## Risks and limitations
- A reserved skeleton can slightly over- or under-estimate the final loaded height if the loaded shape varies.
- Removing stale theme CSS too early could be risky if the new stylesheet fails to load; the source patch removes the old links only after the new one loads.
- Hoisting a null guard changes when the lazy chunk is requested, so it should only be done when the wrapped component truly has nothing to render in the default state.
- The evidence here is improvement-side only; no regression-side PR evidence was provided.

## Anti-pattern evidence
The supplied sources show the opposite of the anti-patterns this technique avoids:

- `returned null until its data ... arrived, then expanded and shoved everything below it down`
- `Suspense fallback reserves a 400px chart-skeleton on every landing-page mount`
- `the 400px placeholder collapses to 0 once the lazy chunk resolves`
- `theme flash` / `FOUC-prevention`

No matched regression PR evidence was found.