---
issue_type: viewport-render-gating
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- viewport_gated_content_identified
- viewport_trigger_is_non_critical
- no_seo_or_analytics_content_hidden
- observer_support_or_fallback_defined
forbidden_techniques:
- pattern: display\s*:\s*none
  reason: Don't hide the gated content with display:none — it removes the element
    from layout and can break measurement, focus, and reveal timing
- pattern: visibility\s*:\s*hidden
  reason: Don't use visibility:hidden as the gating mechanism — it still reserves
    space and does not avoid the initial DOM/render work
- pattern: opacity\s*:\s*0
  reason: Don't gate with opacity:0 — the DOM still renders and paints, so the initial
    work is not reduced
- pattern: IntersectionObserver\s*\(\s*.*threshold\s*:\s*\[\s*0\s*\]
  reason: Don't use a zero-threshold observer for viewport gating — it fires too early
    and defeats the purpose of deferring offscreen rendering
- pattern: react-visibility-sensor|react-intersection-observer
  reason: Don't add a third-party visibility wrapper for this fix — use the platform
    IntersectionObserver directly so the gating logic stays explicit and lightweight
source_prs:
- magento/pwa-studio#3388
- ampproject/amphtml#35835
- carbon-design-system/carbon-addons-iot-react#3114
- toptal/picasso#4572
- dailydotdev/apps#3717
---
# Viewport render gating

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** LCP, INP

## What this addresses

Some navigation, filter, carousel, and secondary content is expensive to build or hydrate, but not needed for the first viewport. Deferring that work until the element is near the viewport can reduce initial DOM creation, layout, and event wiring, which can improve LCP and INP.

## When to apply / when to skip
**Apply when:**
- The content is below the fold or otherwise not needed for first interaction
- The gated subtree is expensive to render, hydrate, or attach listeners to
- The reveal can happen safely when the user scrolls near it
- A fallback placeholder can preserve layout and affordance until reveal

**Skip when:**
- The content is the primary navigation, hero, or another first-viewport critical element
- The content must exist immediately for SEO, accessibility, or analytics correctness
- The gated subtree is tiny and the observer overhead would outweigh the savings
- The component already renders only on demand through a separate interaction path
- The browser support story is undefined and no fallback is planned

## Recommended approaches

### Gate a non-critical subtree with `IntersectionObserver`

```html
<!-- Good: reserve space, then render the expensive subtree only when near viewport -->
<div class="nav-shell" data-nav-shell>
  <button type="button" class="nav-toggle" aria-expanded="false">
    Browse categories
  </button>
  <div class="nav-placeholder" aria-hidden="true"></div>
</div>
```

```javascript
export default function decorate(block) {
  const shell = block.querySelector('[data-nav-shell]');
  const placeholder = shell.querySelector('.nav-placeholder');

  const reveal = async () => {
    const { default: renderNav } = await import('./render-nav.js');
    renderNav(shell);
  };

  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      observer.disconnect();
      reveal();
    }
  }, { rootMargin: '200px 0px' });

  observer.observe(placeholder);
}
```

This keeps the initial DOM light and defers the expensive work until the browser predicts the content is about to matter. A small root margin helps avoid a visible pop-in while still skipping offscreen work.

### Keep a stable placeholder for layout and affordance

```html
<!-- Good: placeholder preserves space and avoids layout jumps -->
<div class="filters">
  <div class="filters-skeleton" aria-hidden="true">
    <span></span><span></span><span></span>
  </div>
</div>
```

```css
.filters-skeleton {
  min-height: 120px;
}
```

A stable placeholder prevents layout shift while the real controls are deferred. This is especially important when the gated content sits above other interactive content.

### CS / AMS: render the shell in HTL, hydrate the heavy part later

```html
<!-- Good: HTL shell stays in the page, heavy markup is injected only when needed -->
<sly data-sly-use.model="com.example.core.models.FilterNavModel" />
<div class="filter-nav" data-filter-nav>
  <button type="button" class="filter-nav__toggle" aria-expanded="false">
    Filters
  </button>
  <div class="filter-nav__placeholder" aria-hidden="true"></div>
</div>
```

```javascript
export default function decorate(block) {
  const placeholder = block.querySelector('.filter-nav__placeholder');

  const observer = new IntersectionObserver(async ([entry]) => {
    if (!entry.isIntersecting) return;
    observer.disconnect();

    const { default: initFilterNav } = await import('./filter-nav.js');
    initFilterNav(block);
  }, { rootMargin: '150px 0px' });

  observer.observe(placeholder);
}
```

This pattern keeps AEM markup predictable while still deferring the expensive client-side work until the component is relevant.

## Anti-patterns

### Hiding the subtree with CSS instead of deferring it

```html
<!-- Bad -->
<div class="filters" style="display:none">
  <button>Price</button>
  <button>Brand</button>
  <button>Size</button>
</div>
```

**Why this is bad:** The content is still created in the DOM, so you do not actually avoid the initial render cost; you also risk focus and accessibility problems when the content is revealed.

### Rendering the full interactive tree immediately and only toggling opacity

```html
<!-- Bad -->
<div class="mega-nav" style="opacity:0">
  <a href="/women">Women</a>
  <a href="/men">Men</a>
  <a href="/kids">Kids</a>
</div>
```

**Why this is bad:** The browser still pays the cost to build, style, and often lay out the subtree, so the expensive work is not deferred.

### Using a zero-threshold observer that fires too early

```javascript
// Bad
const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting) {
    renderFilters();
  }
}, { threshold: [0] });
```

**Why this is bad:** A zero-threshold observer can trigger as soon as a single pixel intersects, which may be too early to be a useful gating signal.

### Gating primary navigation or other first-viewport content

```html
<!-- Bad -->
<div class="site-nav" data-nav-shell>
  <a href="/shop">Shop</a>
  <a href="/support">Support</a>
  <a href="/account">Account</a>
</div>
```

```javascript
// Bad
export default function decorate(block) {
  const observer = new IntersectionObserver(() => {
    block.innerHTML = '<a href="/shop">Shop</a><a href="/support">Support</a>';
  });
  observer.observe(block);
}
```

**Why this is bad:** Primary navigation must be available immediately for usability, accessibility, and crawlability; deferring it can harm both user experience and site semantics.

### Using a third-party visibility wrapper for simple viewport gating

```javascript
// Bad
import { useInView } from 'react-intersection-observer';

const { ref, inView } = useInView();
```

**Why this is bad:** Extra abstraction adds dependency weight and hides the reveal timing, while the platform `IntersectionObserver` is sufficient and easier to reason about in AEM delivery code.

## Flavor-specific notes

### EDS

Use block-local `decorate(block)` logic and `import()` for the heavy subtree. EDS is the best fit for this pattern because the block can keep a lightweight shell in the initial HTML and load the expensive code only when the block approaches the viewport.

Prefer observing a placeholder or shell element rather than the whole block when the block contains multiple interactive regions. If the gated content is a navigation or filter panel, keep the first paint shell accessible and reserve space so the page does not jump when the real content is injected.

### CS

Use HTL for the shell and a clientlib or component script for the deferred behavior. The shell should remain in the template so the page structure is stable, while the expensive markup or hydration logic is delayed until the observer fires.

If the gated content is authored in a reusable component, make sure the component still renders a meaningful placeholder in the initial server response. Do not defer content that is required for page indexing or for the page's primary navigation path.

### AMS

Keep the initial JSP/HTL output minimal and avoid building the full subtree in server-side includes if it is not needed above the fold. The observer should only gate secondary UI, not core navigation or critical page controls.

If the component is delivered through a clientlib, ensure the deferred script is not pulled into the head bundle. The goal is to reduce initial DOM and execution work, not merely move the same cost earlier in the page lifecycle.

### Headless

Use this pattern only when the client application owns the viewport logic and the content is not required for the initial route render. The server should still provide a stable shell or placeholder so the client can hydrate or mount the deferred subtree without layout instability.