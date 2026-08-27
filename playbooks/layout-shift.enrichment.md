### Reserve the final rendered size for toggled media/icon variants

When a component can render different media variants or icon treatments at runtime, reserve the final box up front and keep the variant-specific sizing inside the component tree. This can help prevent a late image/icon swap from changing the component’s outer dimensions after first paint.

```html
<!-- Good — wrapper reserves the expected size -->
<div class="attachment-shell attachment-shell--video">
  <img class="attachment-media" src="/media/preview.jpg" alt="" />
</div>
```

```css
.attachment-shell {
  width: 100%;
  min-height: 240px;
}

.attachment-shell--image {
  min-height: 180px;
}

.attachment-media {
  display: block;
  width: 100%;
  height: auto;
}

.attachment-icon {
  width: 32px;
  height: 32px;
  display: block;
}
```

### Reserve header/promo height when the header becomes sticky or gains promo content

If a header can switch into a sticky/fixed state or conditionally show a promo bar, reserve the combined header height in the authored layout instead of letting the header collapse and then re-expand on scroll or on viewport changes. This can help keep the scroll transition layout-neutral.

```css
/* Good — reserve the full header height up front */
.global-navigation {
  min-height: calc(var(--global-height-nav) + var(--global-height-navPromo));
}

.global-navigation .aside.promobar {
  z-index: 1;
}
```

```js
// EDS-style decorate() hook
export default function decorate(block) {
  const header = document.querySelector('.global-navigation');
  if (!header) return;

  const hasPromo = Boolean(block.querySelector('[data-promo]'));
  header.classList.toggle('has-promo', hasPromo);
}
```