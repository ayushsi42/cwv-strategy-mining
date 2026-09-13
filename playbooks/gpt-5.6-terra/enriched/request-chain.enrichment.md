### Remove an application-level preflight request

When a client performs a route or configuration preflight before requesting page data, consider returning the route or configuration decision with the page-data response. Do not use a separate application request solely to decide whether the data request can begin.

> This applies to application-level “preflight” endpoints, not browser-managed CORS `OPTIONS` preflight requests.

**Bad:**

```javascript
// The page-data request cannot start until config resolves.
export default async function decorate(block) {
  const slug = block.dataset.slug;

  const configResponse = await fetch(`/api/routes/${encodeURIComponent(slug)}`);
  if (!configResponse.ok) throw new Error('Unable to load route configuration');

  const { renderPath } = await configResponse.json();

  const pageResponse = await fetch(`/api/page/${encodeURIComponent(slug)}`);
  if (!pageResponse.ok) throw new Error('Unable to load page data');

  const page = await pageResponse.json();
  block.classList.add(`page-${renderPath}`);
  block.append(Object.assign(document.createElement('h1'), { textContent: page.title }));
}
```

**Why this is bad:** In the simple SSR/SSG scenario described by the evidence, a dedicated preflight followed by a data request produces two synchronous serial requests before rendering can proceed.

**Good:**

```javascript
// One response contains both page data and the render decision.
export default async function decorate(block) {
  const slug = block.dataset.slug;
  const response = await fetch(`/api/page/${encodeURIComponent(slug)}`);

  if (!response.ok) throw new Error('Unable to load page data');

  const { title, renderPath = 'default' } = await response.json();

  block.classList.add(`page-${renderPath}`);
  block.append(Object.assign(document.createElement('h1'), { textContent: title }));
}
```

Update the endpoint so that it preserves the rewrite, routing, or configuration semantics previously supplied by the preflight while returning the requested page data.

> **Source PRs** — **approach:** scalableminds/webknossos#5993, vercel/next.js#37490, digitalfabrik/integreat-app#942, elastic/kibana#161144, next-step/react-gift-product-detail#121 · **anti-pattern:** xmtp/xmtp-js#185, platform-q-ai/jarga-admin#79, vorausrobotik/vdoc#128, Voog/design-nuuk#69