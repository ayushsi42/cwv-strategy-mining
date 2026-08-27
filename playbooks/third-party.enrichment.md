### Load martech after a post-LCP event

Use a dedicated post-LCP hook to start non-critical martech and experimentation code after the page has painted its largest content, instead of tying those loads to the initial render path.

```html
<!-- EDS: fire a custom post-LCP event, then lazy-load martech -->
<script>
  window.addEventListener('load', () => {
    const po = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (!last) return;

      window.dispatchEvent(new CustomEvent('post-lcp'));
      po.disconnect();
    });

    po.observe({ type: 'largest-contentful-paint', buffered: true });
  });

  window.addEventListener('post-lcp', () => {
    const s = document.createElement('script');
    s.src = '/scripts/martech.js';
    s.async = true;
    document.head.appendChild(s);
  }, { once: true });
</script>
```

This can help when experimentation or analytics can wait until after LCP, so the initial render is not delayed by martech setup.

### Lazy-load non-critical UI instrumentation

If a script is only needed for diagnostics or secondary UI behavior, load it after the main page is interactive rather than in the critical path.

```html
<!-- CS/AMS: clientlib loaded after initial render -->
<ui:includeClientLib categories="site.core" />
<script>
  window.addEventListener('load', () => {
    (window.requestIdleCallback || function (cb) { setTimeout(cb, 1); })(() => {
      const s = document.createElement('script');
      s.src = '/etc.clientlibs/site/clientlibs/ui-instrumentation.min.js';
      s.async = true;
      document.head.appendChild(s);
    });
  });
</script>
```

This keeps non-essential instrumentation out of the LCP path while still allowing it to run later for monitoring or debugging.