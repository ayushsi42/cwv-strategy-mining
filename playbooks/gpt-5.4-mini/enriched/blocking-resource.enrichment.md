### Split critical and deferred CSS

When a stylesheet is large but only part of it is needed for first paint, split it into a small critical file that loads immediately and a deferred file for below-the-fold styles. This can help the render path and initial rendering.

```html
<!-- Good -->
<link rel="stylesheet" href="/styles/critical.css">
<link rel="preload" href="/styles/deferred.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="/styles/deferred.css"></noscript>
```

### Avoid async CSS loading that causes flash of unstyled content

```html
<!-- Bad -->
<link rel="stylesheet" href="/styles/main.css" media="print" onload="this.media='all'">
```

**Why this is bad:** It delays the stylesheet until after initial render, which can produce a flash of unstyled content and layout shift when the CSS finally applies.

> **Source PRs** — **approach:** neilotoole/sq#572, cashapp/misk#2800, vikejs/vike#1271, adobecom/milo#133, adobecom/milo#2533 · **anti-pattern:** mempool/mempool#806