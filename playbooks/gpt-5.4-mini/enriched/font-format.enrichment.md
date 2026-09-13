### Self-hosted WOFF2 preload with `@font-face`

When a font is self-hosted and already available as WOFF2, preload the exact file in the document head and pair it with a local `@font-face` rule so the browser can fetch the font early without relying on a third-party stylesheet.

```html
<!-- EDS / static HTML -->
<link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossorigin />
<link rel="stylesheet" href="/fonts.css" />
```

```css
/* fonts.css */
@font-face {
  font-family: "Inter";
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: local("Inter"), url("/fonts/inter.woff2") format("woff2");
}
```

### Avoid removing CDN font connection hints without replacing the font delivery path

If you replace a CDN-hosted font stylesheet with a self-hosted font, make sure the new local font path and preload are in place before removing the CDN `preconnect` / stylesheet references. Otherwise the page can lose the optimized font delivery path and regress text rendering.

```html
<!-- Bad -->
<link rel="dns-prefetch" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter&display=swap" />
<!-- removed, but no replacement font preload or self-hosted font stylesheet added -->
```

**Why this is bad:** Removing the CDN stylesheet and connection hints without adding a working self-hosted font path can delay font fetches and regress text rendering.

```html
<!-- Good -->
<link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossorigin />
<link rel="stylesheet" href="/fonts.css" />
```

```css
/* fonts.css */
@font-face {
  font-family: "Inter";
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url("/fonts/inter.woff2") format("woff2");
}
```

> **Source PRs** — **approach:** CareerCatalyst/Career-Catalyst#4, allcll/allcll-frontend#334, actualbudget/actual#444, expressjs/expressjs.com#1999, UMAprotocol/optimistic-oracle-dapp#20 · **anti-pattern:** lifeisbeautifu1/modern-react-app#61