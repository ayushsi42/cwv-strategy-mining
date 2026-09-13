### Queue consent-gated tracking behind a consent-ready event

```html
<script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js" defer></script>
<script>
  window.consentReady = new Promise((resolve) => {
    window.addEventListener('consent:granted', resolve, { once: true });
  });

  window.consentReady.then(() => {
    const s = document.createElement('script');
    s.src = 'https://www.google-analytics.com/analytics.js';
    s.async = true;
    document.head.appendChild(s);
  });
</script>
```

Use this pattern when the consent manager can load deferred, but analytics or other tracking must not fire until consent is established. The key is gating the tracker on a consent event, not making the consent banner itself synchronous.

### Lazy-load third-party widgets after initial render

```html
<script>
  window.addEventListener('load', () => {
    setTimeout(() => {
      const s = document.createElement('script');
      s.src = 'https://livechat.example.com/widget.js';
      s.async = true;
      document.head.appendChild(s);
    }, 3000);
  });
</script>
```

This is appropriate for below-the-fold third-parties such as chat widgets, social embeds, or other non-essential SDKs that can initialize after the page is usable.

> **Source PRs** — **approach:** viscalyx/viscalyx.se#109, woowacourse/perf-basecamp#184, intellieffect/agentic-cms#1, ibenian/algebench#123, elastic/kibana#139212 · **anti-pattern:** ahmadk953/tasko#926, synapsecns/sanguine#3235, ant-design/x#375, ant-design/ant-design#52300