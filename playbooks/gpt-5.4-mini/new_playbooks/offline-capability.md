---
issue_type: offline-capability
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- service_worker_entrypoint_identified
- precache_scope_confirmed
- offline_fallback_route_defined
- update_strategy_reviewed
forbidden_techniques:
- pattern: navigator\.serviceWorker\.register\s*\(\s*["'][^"']*["']\s*\)\s*;?\s*$
  reason: Don't add a bare service worker registration without precache/offline/update
    handling — it creates maintenance risk without a complete offline strategy
- pattern: workbox-precaching
  reason: Don't introduce precaching unless the app has a validated offline shell
    and cache invalidation plan
- pattern: beforeinstallprompt
  reason: Don't conflate install-prompt UX with offline capability — install prompts
    are a separate feature and do not prove offline support
- pattern: manifest\.json
  reason: Don't treat a web manifest as an offline fix — it only affects install metadata,
    not runtime caching or offline behavior
source_prs:
- botllybot-prog/chatwhash#5
- lifeisbeautifu1/modern-react-app#58
- dokterbob/mutuvia#80
- echo-webkom/echo-web-frontend#892
- vtex-sites/base.store#348
- ShorttRyan/receta#24
- ShorttRyan/receta#26
- ShorttRyan/receta#37
- ukraine-taskforce/s2-sos-app-frontend#1
- alexmojaki/futurecoder#320
- cse112-sp22-group4/Electric-Pomato#107
- ElMassimo/iles#127
- reactplay/react-play#360
- politics-rewired/Spoke#1359
- pluralsh/plural#454
- calovey/FlightApp#1
- Dilven/solidgate#9
- woowacourse/perf-basecamp#112
- dailydotdev/apps#3901
- ITISFoundation/osparc-simcore#7487
---
# Offline capability

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** none directly

## What this addresses

Offline capability changes browser-runtime behavior by adding a service worker, precaching, and cache/update logic. This can improve repeat-load resilience and perceived speed after the first visit, but it does not directly target a single CWV metric.

## When to apply / when to skip
**Apply when:**
- The change adds or modifies a service worker registration
- The change precaches app shell assets or API responses for offline use
- The app needs a defined offline fallback, stale-content strategy, or update flow
- You can identify the exact entrypoint that controls registration and cache scope

**Skip when:**
- The change is only adding a web manifest, icons, or install badge
- The app already has a service worker and the issue is unrelated to caching/offline behavior
- The requested change is purely install UX (`beforeinstallprompt`, home-screen prompt, badge)
- The deployment model cannot support a stable offline shell or cache invalidation plan
- The app is server-rendered in a way that makes offline behavior page-specific and untestable without a dedicated fallback route

## Recommended approaches

### Register a service worker only when the offline shell is defined

```ts
// Good: register once, after the app shell and offline strategy are known
if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    const registration = await navigator.serviceWorker.register("/sw.js");
    await registration.update();
  });
}
```

This keeps registration tied to the actual runtime entrypoint and avoids registering a worker before the app knows what it should cache. Calling `update()` gives the browser a chance to pick up a new worker on repeat visits.

### Precache a bounded app shell and provide an offline fallback

```js
import { decorate } from "./decorate.js";

export default function decorate(block) {
  const status = document.createElement("p");
  status.className = "offline-status";
  status.textContent = "Offline support is enabled for this shell.";
  block.append(status);
}
```

A bounded offline shell keeps the cache predictable and reduces the chance of shipping stale or oversized assets. A navigation fallback strategy ensures the app still renders when the network is unavailable.

### Provide an explicit offline page or shell state

```html
<!-- Good: offline fallback page -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Offline</title>
  </head>
  <body>
    <main>
      <h1>You’re offline</h1>
      <p>Please reconnect to continue.</p>
    </main>
  </body>
</html>
```

A dedicated fallback makes the failure mode understandable instead of leaving the user with a blank screen or a broken navigation state.

## Anti-patterns

### Adding a manifest and calling it offline support

```html
<!-- Bad -->
<link rel="icon" href="/icon-192.png">
<link rel="apple-touch-icon" href="/icon-192.png">
```

**Why this is bad:** A manifest only describes install metadata; it does not cache assets, intercept requests, or make the app work offline.

### Registering a service worker with no cache strategy

```ts
// Bad
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}
```

**Why this is bad:** A bare registration can leave the app in an undefined state where updates, precaching, and offline fallback behavior are all missing.

### Precaching everything without a scope plan

```js
export default function decorate(block) {
  const items = [
    "/index.html",
    "/main.js",
    "/api/data",
    "/images/hero.jpg",
    "/images/gallery-1.jpg",
    "/images/gallery-2.jpg",
  ];

  const list = document.createElement("ul");
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.append(li);
  });
  block.append(list);
}
```

**Why this is bad:** Overbroad caching increases storage pressure and can make stale-content bugs harder to reason about; offline support should be intentionally scoped to the shell and critical assets.

### Treating install UX as the offline fix

```ts
// Bad
window.addEventListener("click", () => {
  showInstallBanner();
});
```

**Why this is bad:** An install prompt improves discoverability of PWA installation, but it does not prove the app has a working offline cache or update strategy.

## Flavor-specific notes

### EDS

Use the block or site entrypoint that already bootstraps client-side behavior. If the site is block-driven, keep the service worker registration in the shared runtime entry rather than in a per-block file, and make the offline fallback route explicit in the site shell.

### CS

Register the service worker from the client-side bootstrap that runs on publish, not from author-only code. If the app uses clientlibs, keep the registration in a clientlib `.content.xml` definition that is included only on publish pages that should participate in offline caching, and verify dispatcher/CDN caching does not conflict with the worker’s cache names.

### AMS

Place registration in the publish-side JS entrypoint or clientlib that is actually delivered to end users. Validate that the offline fallback page is reachable through the same publish path and that legacy dispatcher rules do not strip the service worker or manifest responses.

### Headless

Offline capability is usually implemented in the frontend shell, not in the CMS content layer. Keep the service worker scope aligned with the app origin and verify API responses have a clear stale-while-revalidate or network-first policy before precaching any data.