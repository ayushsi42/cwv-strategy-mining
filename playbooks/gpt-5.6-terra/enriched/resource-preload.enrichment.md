### Preload a stylesheet before applying it

```html
<link
  rel="preload"
  href="/etc.clientlibs/my-site/clientlibs/clientlib-critical.min.css"
  as="style">
<link
  rel="stylesheet"
  href="/etc.clientlibs/my-site/clientlibs/clientlib-critical.min.css">
```

> **Source PRs** — **approach:** Shopify/dawn#2258, Quansight/ragna#312, scandipwa/scandipwa#3139, phillipc0/WA-DP#113, cfpb/hmda-frontend#2180