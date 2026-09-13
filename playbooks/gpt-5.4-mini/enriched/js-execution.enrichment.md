### Lazy-load heavy initialization after first paint

If a feature’s expensive setup is not required for the initial HTML or first paint, move that work out of the critical path and trigger it after render. Use a browser API that runs after the page is interactive, and keep the initial render lightweight.

```html
<!-- Good — defer non-critical initialization until after the initial render -->
<script>
  window.addEventListener('load', () => {
    if ('requestIdleCallback' in window) {
      requestIdleCallback(() => {
        initializeHeavyFeature();
      });
    } else {
      setTimeout(() => {
        initializeHeavyFeature();
      }, 0);
    }
  });
</script>
```

Use this when the work can safely wait until after the initial render and the UI can show a lightweight placeholder or default state until initialization completes.

### Avoid doing expensive setup during render

If the work is needed only after the page is visible, do not perform it as part of render or synchronous module initialization.

```html
<!-- Bad — heavy work runs during the critical render path -->
<script>
  document.addEventListener('DOMContentLoaded', () => {
    initializeHeavyFeature();
  });
</script>
```

**Why this is bad:** Running expensive setup during render or synchronous startup can increase main-thread blocking and delay first paint.

> **Source PRs** — **approach:** atlassian-labs/react-loosely-lazy#94, elastic/kibana#161144, mucommander/mucommander#1044, code-dot-org/code-dot-org#60463, okTurtles/group-income#2357 · **anti-pattern:** kamiazya/web-csv-toolbox#551