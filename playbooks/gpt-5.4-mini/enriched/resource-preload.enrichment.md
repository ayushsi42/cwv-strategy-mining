### Preload critical CSS

When the HTML shell already knows it needs a stable stylesheet before first paint, preload the CSS file from the document and keep the stylesheet link in place so the browser can apply it once fetched.

```html
<!-- Good -->
<link rel="preload" href="/styles/landing.css" as="style">
<link rel="stylesheet" href="/styles/landing.css">
```

The preload starts the fetch early; the stylesheet link applies the styles. Both are needed — preload alone doesn't apply the CSS.

> **Source PRs** — **approach:** ls1intum/Artemis#12541, ParabolInc/parabol#6251, Shopify/dawn#2258, AndreiSalnikov/count-your-spendings#1, nestoririondo/typescript-webshop-front#5