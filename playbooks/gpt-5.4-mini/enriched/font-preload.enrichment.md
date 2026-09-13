### Preloading only the above-the-fold font faces

> **Use preload only for a small, human-judged set of display-critical fonts.** For the common case, use [`font-fallback.md`](./font-fallback.md) instead.

#### Good example

```html
<head>
  <link rel="preload" href="/fonts/lato/lato-regular.woff2" as="font" crossorigin>
  <link rel="preload" href="/fonts/oswald/oswaldregular.woff2" as="font" crossorigin>
</head>
```

Use this when the page truly depends on a small set of critical fonts in the initial viewport, and the font URLs are stable. Keep the set to one or two faces where possible; preload bandwidth competes with other critical resources.

#### Bad example

```html
<head>
  <link rel="preload" href="/fonts/lato/lato-regular.woff2?v=123" as="font" type="font/woff2">
  <link rel="preload" href="/fonts/oswald/oswaldregular.woff2" as="font" type="font/woff2" crossorigin="anonymous">
  <link rel="preload" href="/fonts/oswald/oswaldmedium.woff2" as="font" type="font/woff2" crossorigin="anonymous">
  <link rel="preload" href="/fonts/oswald/oswaldbold.woff2" as="font" type="font/woff2" crossorigin="anonymous">
</head>
```

**Why this is bad:**  
- The first preload is missing `crossorigin`, so the browser can open a second connection and fetch the font twice.  
- The first preload also uses a cache-busted query string, which makes the preload URL unstable across builds.  
- Preloading too many faces increases bandwidth contention and can delay other critical resources.

> **Source PRs** — **approach:** RomanShemelin/e-commerce#1, htmlacademy-adaptive/2280491-cat-energy-28#9, eman-maheen/auxcube#1, woowacourse/perf-basecamp#121, harvard-lil/h2o#1910