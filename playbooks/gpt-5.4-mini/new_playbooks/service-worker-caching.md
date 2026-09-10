---
issue_type: service-worker-caching
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- lifeisbeautifu1/modern-react-app#58
- nasa-gibs/worldview#3803
- echo-webkom/echo-web-frontend#892
- alexmojaki/futurecoder#320
- cse112-sp22-group4/Electric-Pomato#107
- ElMassimo/iles#127
- reactplay/react-play#360
- politics-rewired/Spoke#1359
- pluralsh/plural#454
- calovey/FlightApp#1
- woowacourse/perf-basecamp#112
---
# Service worker caching

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** LCP, TTFB

## What this addresses

A service worker can cache the app shell, static assets, and selected runtime responses so repeat visits avoid full network fetches. That can reduce repeat-load latency, which may improve LCP and perceived TTFB on subsequent navigations.

This is a browser-runtime change, not a markup-only optimization: it affects how requests are intercepted after the page loads, so it needs careful scope, update, and offline behavior.

## When to apply / when to skip
**Apply when:**
- The site has a stable app shell or repeat-visit asset set that benefits from offline/runtime caching
- The target pages are served from a browser app shell or SPA-like shell, or otherwise have a clear static asset set to precache
- You can define which requests are safe to cache and how they are updated on deploy
- Manifest registration and service worker scope are both available in the delivery path

**Skip when:**
- The site is EDS, where this playbook does not apply
- The app has no stable repeat-visit shell or the content is highly personalized and uncacheable
- The fix would cache authenticated, user-specific, or mutation-heavy responses
- You cannot verify cache invalidation, versioning, or offline fallback behavior
- The only goal is installability; a manifest alone does not address repeat-load CWV

## Recommended approaches

### Precache the app shell and immutable build assets

Use a service worker to precache the shell and hashed static assets, then serve them from cache on repeat visits.

```js
// Good: service-worker.js
import { precacheAndRoute } from 'workbox-precaching';
import { clientsClaim } from 'workbox-core';

self.skipWaiting();
clientsClaim();

precacheAndRoute(self.__WB_MANIFEST);
```

```js
// Good: register once from the app entry
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js');
  });
}
```

This works because immutable build assets can be cached aggressively without risking stale content, while the app shell loads quickly on repeat visits.

### Cache selected runtime GET requests with a bounded strategy

Use a runtime caching strategy for safe, cacheable GET requests such as public API responses or image assets.

```js
// Good: runtime caching for safe public GETs
import { registerRoute } from 'workbox-routing';
import { StaleWhileRevalidate } from 'workbox-strategies';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { ExpirationPlugin } from 'workbox-expiration';

registerRoute(
  ({ request, url }) => request.method === 'GET' && url.pathname.startsWith('/api/public/'),
  new StaleWhileRevalidate({
    cacheName: 'public-api-v1',
    plugins: [
      new CacheableResponsePlugin({ statuses: [200] }),
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 }),
    ],
  })
);
```

This can improve repeat-load performance without turning every response into a permanent cache entry.

### Pair caching with a manifest and explicit registration

If the app is intended to be installable, register the manifest and service worker together.

```html
<!-- Good -->
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0b3d91">
```

```js
// Good
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js');
}
```

The manifest handles installability metadata; the service worker handles caching behavior. Keeping both explicit makes the PWA behavior predictable.

## Anti-patterns

### Registering a service worker with no caching plan

```js
// Bad
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js');
}
```

**Why this is bad:** Registration alone does not improve repeat-load performance; without precaching or runtime caching, it adds complexity and can still leave repeat visits fully network-bound.

### Caching everything indiscriminately

```js
// Bad
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.open('app-cache').then(async (cache) => {
      const cached = await cache.match(event.request);
      if (cached) return cached;
      const response = await fetch(event.request);
      cache.put(event.request, response.clone());
      return response;
    })
  );
});
```

**Why this is bad:** Caching every request can store personalized, error, or opaque responses and makes invalidation unpredictable, which can break updates and serve stale content.

### Adding only a manifest and calling it PWA caching

```html
<!-- Bad -->
<link rel="manifest" href="/manifest.json">
```

**Why this is bad:** A manifest enables installability metadata, but it does not cache the app shell or assets, so repeat-visit CWV does not improve by itself.

### Caching authenticated or user-specific responses

```js
// Bad
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new CacheFirst({ cacheName: 'api-cache' })
);
```

**Why this is bad:** User-specific API responses can become stale or leak across sessions, which is a correctness and privacy risk, not a performance win.

## Flavor-specific notes

### CS

Prefer Workbox or equivalent build-integrated service worker generation so the app shell and hashed client assets can be precached from the build output. Register the service worker from the client entry point after the app bootstraps, and keep the cache scope aligned with the publish path.

For AEM CS, the most common safe targets are:
- hashed clientlib or frontend bundle assets
- public, cacheable JSON endpoints
- static shell routes that do not depend on authoring-time personalization

If the site already uses a manifest, verify that the service worker scope covers the same path prefix as the shell and that deploys invalidate the precache manifest.

### AMS

Use a conservative caching strategy because legacy stacks often mix static shell assets with server-rendered pages and session-dependent content. Cache only immutable assets and explicitly public GET endpoints.

If the app is delivered through a servlet or JSP shell, verify:
- the service worker file is served from a scope that matches the app root
- the shell can be loaded offline or from cache without breaking login or form submission flows
- dispatcher or CDN headers do not prevent the worker script and manifest from being fetched

### Headless

This applies when the headless frontend has a stable shell and a clear asset pipeline. Cache the shell, route-level JS/CSS, and safe public API responses; do not cache authenticated content or mutation responses.

For headless apps, the key validation is whether the repeat-visit path is dominated by static shell and public data fetches. If the app is mostly personalized or session-bound, skip auto-fix and recommend a manual caching design instead.