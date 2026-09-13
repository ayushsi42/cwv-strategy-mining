---
issue_type: deferred-rendering
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- noncritical_content_confirmed
- initial_viewport_content_not_deferred
- ssr_or_server_markup_preserved
- idle_fallback_available
- interaction_path_not_delayed
- no_existing_client_only_placeholder_dependency
forbidden_techniques:
- pattern: requestIdleCallback\s*\(\s*.*render
  reason: Don't move critical or above-the-fold rendering into requestIdleCallback
    — it can delay first paint and hurt LCP/INP instead of improving responsiveness
- pattern: requestAnimationFrame\s*\(\s*\(\s*\)\s*=>\s*requestAnimationFrame\s*\(
  reason: Don't stack double requestAnimationFrame for component rendering — it adds
    avoidable latency and is too coarse for deferred UI work
- pattern: setTimeout\s*\(\s*.*render
  reason: Don't use arbitrary timeouts to defer rendering — they are not tied to browser
    idle time and can fire during user input
- pattern: client:visible
  reason: Headless delivery does not use Astro-style client directives — use the platform's
    native deferred-rendering mechanism instead
source_prs:
- woowacourse/perf-basecamp#172
- Comfy-Org/ComfyUI_frontend#11273
- otomatty/portfolio#39
- nuxt/framework#5689
- Scrivito/scrivito_example_app_js#494
- GoogleChrome/web.dev#9409
- pinterest/gestalt#2737
- nuxt/nuxt#19231
- shopsys/shopsys#3089
- nuxt/nuxt#26468
- ForumMagnum/ForumMagnum#9502
- SalesforceCommerceCloud/pwa-kit#2696
- Jahia/javascript-modules#447
---
# Deferred rendering

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** INP, TBT

## What this addresses

Some components are not needed for the first meaningful paint or the first interaction target. Deferring their render work until the browser is idle can reduce main-thread contention during startup and can improve INP by keeping input handlers from competing with expensive component work.

This is a runtime scheduling fix, not a code-splitting fix: the goal is to postpone rendering/hydration of noncritical UI, while still preserving a usable fallback or server-rendered shell.

## When to apply / when to skip
**Apply when:**
- The component is below the fold, secondary, or otherwise noncritical to the initial viewport
- The deferred work is render/hydration cost, not data correctness or SEO-critical content
- A stable fallback, placeholder, or server-rendered shell can be shown immediately
- The page has measurable main-thread contention during startup or early interaction

**Skip when:**
- The component is in the initial viewport or is part of the primary interaction path
- Deferring it would hide the LCP element, delay first input affordance, or cause layout instability
- The work is already cheap enough that scheduling overhead would outweigh the benefit
- The component must be interactive immediately for accessibility, navigation, consent, or form submission
- The page relies on the component for server-rendered content that must be present for indexing or core UX

## Recommended approaches

### Defer noncritical client work until idle, with a visible fallback

```javascript
// Good: EDS block example
export default function decorate(block) {
  const fallback = block.querySelector('[data-fallback]');
  const mount = async () => {
    const { decorateDeferred } = await import('./deferred-widget.js');
    decorateDeferred(block);
  };

  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      mount();
    }, { timeout: 2000 });
  } else {
    window.addEventListener('load', () => {
      mount();
    }, { once: true });
  }

  if (fallback) {
    fallback.hidden = false;
  }
}
```

Use idle time to start the expensive render path only after the browser has handled more urgent work. The fallback keeps the page understandable and avoids a blank gap while the deferred component waits.

### Keep the server-rendered shell, then hydrate or enhance later

```html
<!-- Good: CS / AMS HTL -->
<sly data-sly-use.model="com.example.components.FeatureModel" />
<div class="feature-shell" data-feature-shell>
  <div class="feature-shell__summary">
    ${model.summary}
  </div>
  <div class="feature-shell__deferred" hidden data-feature-deferred>
    ${model.expensiveMarkup}
  </div>
</div>
```

```javascript
// Good: enhance after the browser is idle
const deferred = document.querySelector('[data-feature-deferred]');
if (deferred) {
  const showDeferred = () => {
    deferred.hidden = false;
  };

  if ('requestIdleCallback' in window) {
    requestIdleCallback(showDeferred, { timeout: 1500 });
  } else {
    window.addEventListener('load', showDeferred, { once: true });
  }
}
```

This preserves meaningful HTML for SSR and crawlers while postponing the expensive part of the UI until the browser has breathing room.

### Use a component-specific placeholder instead of blocking the whole page

```javascript
// Good: Headless example
export function DeferredRecommendations({ ready, children }) {
  if (!ready) {
    return (
      <div className="recommendations-skeleton" aria-busy="true" aria-live="polite">
        Loading recommendations…
      </div>
    );
  }

  return <>{children}</>;
}
```

A fallback lets the page paint quickly and keeps the deferred region explicit. The browser can prioritize the important content first, then fill in the secondary UI later.

## Anti-patterns

### Deferring the primary viewport content

```javascript
// Bad
export default function decorate(block) {
  requestIdleCallback(() => {
    block.innerHTML = `
      <h1>Product title</h1>
      <img src="/hero.jpg" alt="Hero">
      <button>Buy now</button>
    `;
  });
}
```

**Why this is bad:** If the component is part of the initial viewport, idle deferral delays the content users need immediately and can push out LCP or first interaction readiness.

### Using double `requestAnimationFrame` as a generic scheduler

```javascript
// Bad
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    renderDeferredWidget();
  });
});
```

**Why this is bad:** Double `requestAnimationFrame` is a blunt delay mechanism, not an idle-aware scheduler, and it can still run during busy periods while adding unnecessary latency.

### Replacing render deferral with arbitrary timeouts

```javascript
// Bad
setTimeout(() => {
  mountHeavyComponent();
}, 3000);
```

**Why this is bad:** Fixed delays are disconnected from actual main-thread pressure, so they may fire during user input or wait far longer than needed on fast pages.

### Hiding interactive controls until deferred render completes

```html
<!-- Bad -->
<button disabled aria-disabled="true">Open filters</button>
<div hidden id="filters-panel"></div>
```

**Why this is bad:** If the control is part of the primary interaction path, disabling it until deferred work finishes hurts responsiveness and can make the page feel broken.

## Flavor-specific notes

### EDS

Use block-level JavaScript and `decorate(block)` as the unit of deferral. Keep the initial HTML meaningful, then lazy-load the expensive enhancement with `import('./deferred-widget.js')` only after the browser is idle. Avoid moving above-the-fold block content behind idle scheduling.

### CS

Prefer preserving server-rendered markup in HTL and deferring only the enhancement layer. If the component is authored through Sling Models, keep the model output available in the initial HTML and gate only the noncritical client behavior behind idle scheduling.

### AMS

Use JSP/HTL output to render the stable shell first, then defer secondary client-side behavior. Be careful with legacy pages where the same component may appear in multiple contexts; validate that the deferred portion is truly noncritical on each template before changing it.

### Headless

Apply this only to client-rendered islands or widgets that are not needed for the first interaction. If the page already uses a framework-specific hydration strategy, prefer the native deferred-rendering primitive for that stack rather than layering custom idle logic on top.