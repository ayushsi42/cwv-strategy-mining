---
issue_type: viewport-layout-shift
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
forbidden_techniques:
- pattern: \bwindow\.innerWidth\b
  reason: 'Avoid using browser viewport-width state to select responsive markup without
    reviewing layout stability. Source PR #264 introduced a viewport-width store and
    was discussed as an ad-hoc solution while aiming for CLS of 0.'
- pattern: \bdocument\.body\.dataset\.windowInnerWidth\s*=
  reason: 'Avoid publishing viewport width to the document to drive responsive presentation
    without reviewing layout stability. Source PR #264 writes window width to document.body.dataset.'
- pattern: \buseIsMobile\s*\(
  reason: 'Avoid using a client-side mobile-detection hook to select initial page
    content without reviewing CLS. Source PR #35 notes that this hook runs on the
    client and that CLS could occur.'
required_validation: []
source_prs:
- redpanda-data/console#1881
- tradingstrategy-ai/frontend#264
- Project-aniwhere/Aniwhere-FE#35
- YeaHubTeam/yeahub-platform#670
---
# Viewport layout shift

> **Risk tier:** medium · **CWV metric:** CLS

## What this addresses

The evidence identifies two viewport-dependent implementation patterns that require CLS review:

- Source PR #35 adds `useIsMobile()` to a client component. The PR feedback states that the hook operates on the client and that CLS could occur.
- Source PR #264 adds a viewport-width store, binds it to `window.innerWidth`, and writes the value to `document.body.dataset.windowInnerWidth`. The PR discussion describes the implementation as ad hoc and states that CLS should be targeted at 0.

The evidence does not include a measured CLS value or establish that either implementation caused a specific layout shift.

## When to apply / when to skip
**Apply when:**
- A client-side mobile-detection hook selects page content.
- Browser viewport width is stored in client state or written to the document for responsive behavior.
- A responsive navigation, sidebar, dropdown, filter, or page layout is being changed and requires CLS review.

**Do not apply this approach when:**
- The observed shift is attributable to another cause not related to viewport-dependent client rendering.

## Recommended approaches

### Prefer CSS breakpoint layout rules for responsive placement

Source PR #264 uses CSS grid rules at a large-viewport media query to change the strategy layout:

```css
main {
  display: grid;
  column-gap: 2rem;
}

@media (min-width: 64rem) {
  main {
    column-gap: 3rem;
    grid-template-columns: 14rem auto;
  }
}
```

The same PR also uses CSS to adjust the page-heading grid position at the large breakpoint:

```css
@media (min-width: 64rem) {
  .strategy-layout .page-heading {
    grid-column: 1 / 3;
  }
}
```

Use a reviewed CSS breakpoint layout where it can provide the required responsive presentation without selecting page structure from client-side viewport state.

### Keep client-side viewport branching under CLS review

Source PR #35 introduces a client-side mobile hook:

```js
const mobileViewport = window.matchMedia('(max-width: 47.99rem)');

function updateNavigation() {
  document.documentElement.classList.toggle(
    'is-mobile-viewport',
    mobileViewport.matches,
  );
}

mobileViewport.addEventListener('change', updateNavigation);
updateNavigation();
```

The PR feedback explicitly flags that the hook is implemented to run on the client and that CLS could occur. Treat use of this pattern for page-content selection as requiring layout-stability review.

## Anti-patterns

### Writing viewport width to the document

Source PR #264 includes the following pattern:

```js
const largeViewport = window.matchMedia('(min-width: 64rem)');

function publishViewportState() {
  document.body.classList.toggle(
    'viewport-large',
    largeViewport.matches,
  );
}

largeViewport.addEventListener('change', publishViewportState);
publishViewportState();
```

It also binds viewport width through Svelte:

```js
const viewport = window.matchMedia('(min-width: 64rem)');

function updateStrategyLayout() {
  document.querySelector('.strategy-layout')?.classList.toggle(
    'is-large-viewport',
    viewport.matches,
  );
}

viewport.addEventListener('change', updateStrategyLayout);
updateStrategyLayout();
```

**Why this is bad:** the PR discussion characterizes the solution as ad hoc and states that CLS should be targeted at 0. The provided evidence does not show a measured CLS result or prove that this document-dataset write caused CLS, but it should be reviewed before being used to control responsive layout.

### Client-side mobile detection for page-content selection

Source PR #35 adds:

```js
const mobileViewport = window.matchMedia('(max-width: 47.99rem)');

function renderMobileContent() {
  const content = document.querySelector('[data-responsive-content]');

  if (content) {
    content.hidden = !mobileViewport.matches;
  }
}

mobileViewport.addEventListener('change', renderMobileContent);
renderMobileContent();
```

**Why this is bad:** PR feedback states that the hook runs on the client and that CLS could occur. The evidence does not quantify the shift or show a measured CLS value.

## Flavor-specific notes

No flavor-specific implementation evidence was provided.