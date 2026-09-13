### Responsive image helper with explicit dimensions

When a project already has a reusable image helper or partial, pass the intrinsic dimensions through that helper so every emitted image reserves space consistently. This is especially useful for responsive images where the helper already knows the largest exported asset and can generate the `srcset` / `sizes` pair.

```js
export default function decorate(block) {
  const picture = block.querySelector('picture');
  if (!picture) return;

  const img = picture.querySelector('img');
  if (!img) return;

  const width = img.getAttribute('width');
  const height = img.getAttribute('height');

  if (width && height) {
    img.setAttribute('width', width);
    img.setAttribute('height', height);
  }
}
```

```html
<picture class="w-1/2 sm:w-full">
  <source srcset="/assets/images/modules/01/example-800.webp 800w" media="(min-width: 650px)" type="image/webp">
  <img src="/assets/images/modules/01/example-800.webp" width="800" height="800" alt="Example">
</picture>
```

**Good example:** Keep the sizing logic centralized in the helper, and emit real `width` and `height` values in the final markup.

**Why this is good:** It avoids repeating image-sizing logic across pages and can help the browser reserve space before the image loads.

> **Source PRs** — **approach:** PrestaShop/PrestaShop#27233, technologiestiftung/service-agentinnen#34, technologiestiftung/service-agentinnen#27, mozilla/bedrock#11994, utmgdsc/website#41 · **anti-pattern:** ant-design/x#708