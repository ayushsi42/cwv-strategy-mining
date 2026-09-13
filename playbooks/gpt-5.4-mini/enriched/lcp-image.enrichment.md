### Client-side-only side effects guard

When a component is rendered in a mixed SSR/CSR app, keep browser-only integrations out of the server render path. Wrap client-only subscriptions or SDK calls behind a client check so they don't execute during SSR and don't add avoidable work to the initial render.

```js
import { onActiveWorkspaceResult } from './workspace.js';

if (typeof window !== 'undefined') {
  onActiveWorkspaceResult(({ data }) => {
    if (data && data.activeUser && data.activeUser.activeWorkspace) {
      window.Intercom('update', {
        company_id: data.activeUser.activeWorkspace.id,
        company_name: data.activeUser.activeWorkspace.name
      });
    }
  });
}
```

### Explicit eager-load toggle for image components

For image components that may be used both above and below the fold, expose an explicit loading prop and default it to eager for critical images. Pass that flag through to the image element so the caller can opt out for non-critical images without changing the component internals.

```html
<!-- Good -->
<img
  src="hero.jpg"
  alt="Hero"
  fetchpriority="high"
  loading="eager"
  width="1200"
  height="800">
```

```html
<!-- Good -->
<img
  src="gallery.jpg"
  alt="Gallery"
  loading="lazy"
  width="800"
  height="600">
```

> **Source PRs** — **approach:** specklesystems/speckle-server#5278, woowacourse/perf-basecamp#163, widgetbot-io/message-renderer#4, guardian/dotcom-rendering#8524, WgtTelia/Telia-e-shop-front-end#11 · **anti-pattern:** HireUsPlease/FGC-Finder#8