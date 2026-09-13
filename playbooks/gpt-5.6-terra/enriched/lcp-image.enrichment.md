### Scope LCP priority in reusable image components

Do not make every instance of a shared image component eager. Mark only an above-the-fold LCP candidate, usually the page hero.

```html
<!-- Bad: every shared image is treated as critical -->
<img src="card-image.jpg"
     alt="Card image"
     loading="eager"
     fetchpriority="high">
```

```html
<!-- Good: only an above-the-fold hero image receives LCP priority -->
<img src="hero.jpg"
     alt="Hero"
     width="1200"
     height="800"
     loading="eager"
     fetchpriority="high">
```

For shared image components, use an explicit property on the single hero image resource.

```html
<!-- Good: shared image component HTL -->
<sly data-sly-test="${properties.lcpImage}">
  <img src="${image.src @ context='uri'}"
       alt="${image.alt}"
       width="${image.width}"
       height="${image.height}"
       loading="eager"
       fetchpriority="high">
</sly>

<sly data-sly-test="${!properties.lcpImage}">
  <img src="${image.src @ context='uri'}"
       alt="${image.alt}"
       width="${image.width}"
       height="${image.height}"
       loading="lazy">
</sly>
```

Set `lcpImage` for the one above-the-fold image that is the LCP candidate. Keep other instances of the reusable component on their normal loading behavior.

> **Source PRs** — **approach:** codeit-bootcamp-frontend/Weekly-Mission#104, dailydotdev/apps#2470, eCOO-FURG/apps#167, woowacourse/perf-basecamp#117, woowacourse/perf-basecamp#176 · **anti-pattern:** oreoorbitz/Dawn-employee-modifcations#2