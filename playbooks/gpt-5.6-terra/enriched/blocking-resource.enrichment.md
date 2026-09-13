### Separate CSS for lazily loaded components

Keep component-specific selectors in CSS that is loaded with lazily loaded components where the build setup supports it. Evidence shows CSS can be separated for lazy-loaded components, while critical styles can be loaded immediately and deferred styles loaded asynchronously.

```js
export default function decorate(block) {
  block.querySelectorAll('a').forEach((link) => {
    link.classList.add('carousel-slide');
  });
}
```

```css
.carousel-slide {
  scroll-snap-align: start;
}
```

Keep shared and critical styles in the immediately loaded stylesheet. Consider keeping CSS for content that appears in the initial viewport in the critical stylesheet.

> **Source PRs** — **approach:** joggrdocs/zpress#28, neilotoole/sq#572, OdyseeTeam/odysee-frontend#2704, OdyseeTeam/odysee-frontend#2747, GoogleChrome/lighthouse#13260