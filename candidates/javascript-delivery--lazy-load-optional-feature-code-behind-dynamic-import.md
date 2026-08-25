---
issue_type: javascript-delivery--lazy-load-optional-feature-code-behind-dynamic-import
parent_strategy: javascript-delivery
risk_tier: low
cwv_metrics:
  - bundle_size_delta_pct
  - performance
source_prs:
  - RedHat-UX/red-hat-design-system#2604
  - woowacourse/perf-basecamp#176
  - atlassian-labs/mermaid-diagrams-viewer#77
required_validation:
  - id: optional_feature_is_not_needed_for_initial_render
    description: Confirm the optional feature is absent from the initial render path and the page/component still renders correctly without loading the optional module.
  - id: dynamic_import_is_guarded_by_feature_presence
    description: Confirm the dynamic import executes only after a real feature signal is present, such as a property value, route boundary, or content detection result.
forbidden_techniques: []
---

# Lazy-load optional feature code behind dynamic import

> **Risk tier:** low · **Parent strategy:** javascript-delivery · **CWV metrics:** bundle_size_delta_pct, performance

## Strategy summary

Defer downloading and executing optional feature code until the feature is actually needed.

This strategy is supported by the evidence in three forms:

- A tab icon module is imported only when an `icon` property is present.
- Route/page components are loaded with `lazy(() => import(...))` and rendered under `Suspense`.
- Optional content handling is separated from unrelated work so the optional path is only used when the content signal is present.

The expected effect is a smaller initial JavaScript payload and less parse/execute work for visitors who never use the optional feature.

## Apply / Skip

### Apply
Use this strategy when all of the following are true:

- The feature is optional and not required for first render.
- A runtime signal can identify when the feature is needed.
- The optional code is large enough that moving it off the initial path can reduce bundle size or execution work.
- The fallback or default state is acceptable without the optional module.

### Skip
Do not use this strategy when any of the following are true:

- The code is required for the initial view or first interaction.
- The feature cannot be detected before loading the module.
- The module is too small for the async boundary to be worthwhile.
- The feature must be available synchronously for startup behavior.

## Required validation IDs

### `optional_feature_is_not_needed_for_initial_render`
Validate that the initial render does not depend on the optional module.

Measurable checks:
- Load the page/component with the optional feature absent.
- Confirm the initial render completes without requesting the optional module.
- Confirm the non-optional UI still renders and remains usable.

Evidence-derived examples:
- Tabs render without loading the icon module until an `icon` value exists.
- Routes render without loading page components until navigation reaches them.

### `dynamic_import_is_guarded_by_feature_presence`
Validate that the import is triggered only after a feature signal is present.

Measurable checks:
- Identify the feature signal used to gate loading.
- Confirm the import does not run when the signal is absent.
- Confirm the import runs when the signal is present.

Evidence-derived examples:
- The icon module is imported only when `this.icon` is truthy.
- Route components are loaded only when the route is reached.
- Optional content handling is triggered only after content detection identifies the relevant content.

## Evidence-derived implementation patterns

### 1) Property-gated dynamic import for optional UI code

Good:

```ts
@observes('icon')
protected iconChanged() {
  if (this.icon) {
    import('@rhds/elements/rh-icon/rh-icon.js');
  }
}
```

Why this fits the evidence:
- The optional icon module is not part of the default render path.
- The import is guarded by a real feature signal: `this.icon`.

Bad:

```ts
import('@rhds/elements/rh-icon/rh-icon.js');
```

Why this does not fit:
- The import runs unconditionally.
- The optional module is requested even when the feature is absent.

### 2) Route-level lazy loading for non-initial pages

Good:

```tsx
import { lazy, Suspense } from 'react';

const Home = lazy(() => import('./pages/Home/Home'));
const Search = lazy(() => import('./pages/Search/Search'));

<Suspense fallback={<div style={{ minHeight: '100vh' }}>Loading...</div>}>
  <Routes>
    <Route path="/" element={<Home />} />
    <Route path="/search" element={<Search />} />
  </Routes>
</Suspense>
```

Why this fits the evidence:
- Page components are not loaded until the route is reached.
- The fallback keeps the UI renderable while the optional chunk loads.

Bad:

```tsx
import Home from './pages/Home/Home';
import Search from './pages/Search/Search';
```

Why this does not fit:
- Both pages are loaded eagerly at startup.
- The optional route code remains on the initial path.

### 3) Content-driven optional handling

Good:
- Detect the optional content type first.
- Load or activate the optional path only after detection succeeds.

Evidence-derived example:
- Mermaid-like code is detected before the mermaid-specific path is used.

Bad:
- Load the optional parser or renderer before checking whether the content actually needs it.

## What to measure

Use the supplied metrics only:

- `bundle_size_delta_pct`
- `performance`

Recommended checks:
- Compare bundle size before and after the change.
- Compare performance before and after the change, especially initial JavaScript execution and payload-related metrics.
- Confirm the optional module is absent from the initial request path when the feature is unused.

## Evidence and inference

### Observed facts
- **RedHat-UX/red-hat-design-system#2604**
  - `<rh-tab>` gained `icon` and `icon-set` support.
  - The icon module is imported only when an icon is present.
- **woowacourse/perf-basecamp#176**
  - Route components were converted to `lazy(() => import(...))`.
  - Rendering is wrapped in `Suspense` with a fallback.
- **atlassian-labs/mermaid-diagrams-viewer#77**
  - Optional content detection was separated from unrelated work.
  - Mermaid-specific handling is only used when the content matches the mermaid signal.

### Inference
- The shared mechanism is not generic “lazy loading” alone.
- The supported pattern is **deferring optional code behind a runtime feature signal**.
- This is appropriate when many users never need the feature, because it can reduce initial JavaScript payload and parse/execute work.

## Risks and limitations

- The async boundary adds lifecycle and fallback complexity.
- If the feature is common on the critical path, deferring it may only shift work later.
- A dynamic import by itself is not sufficient; it must be guarded by a real feature signal.
- The evidence supports this for optional UI features and non-initial routes, not for universally required startup code.

## Confidence

High.

The evidence packet reports:
- 53 observations across 47 repositories
- 90.6% directional consistency
- p25 = 10.02, median = 16.86, p75 = 34.58 for absolute measured delta summary