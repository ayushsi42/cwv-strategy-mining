### Critical CSS split with deferred stylesheet loading

When a stylesheet contains both above-the-fold and below-the-fold rules, split it so the critical rules are delivered immediately and the rest is loaded after first paint.

```html
<!-- Good: critical CSS is render-blocking, deferred CSS is loaded separately -->
<link rel="stylesheet" href="/styles/critical.css">
<link rel="preload" href="/styles/deferred.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="/styles/deferred.css"></noscript>
```

Use this when Lighthouse coverage shows the main stylesheet is carrying non-critical rules that can be moved out of the critical path.

## Anti-patterns

### Loading a full stylesheet with the print-onload swap hack

```html
<!-- Bad: swaps a stylesheet from print to all after load -->
<link rel="stylesheet" href="/styles/app.css" media="print" onload="this.media='all'">
```

**Why this is bad:** This can delay stylesheet application and may interfere with print behavior or create inconsistent rendering. Use a real critical CSS split instead.

## Recommended approaches

### Split critical and non-critical CSS

```html
<!-- Good -->
<link rel="stylesheet" href="/styles/critical.css">
<link rel="preload" href="/styles/non-critical.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="/styles/non-critical.css"></noscript>
```

Keep only above-the-fold rules in `critical.css`, and move the rest to a separate stylesheet that loads after first paint.