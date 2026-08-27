---
issue_type: image-asset-bloat
applicable_flavors: [eds, cs, ams, headless]
risk_tier: medium

required_validation:
  - image_asset_is_lcp_or_above_fold
  - image_dimensions_known_or_reservable
  - replacement_asset_is_smaller_or_equivalent
  - image_not_js_lazy_loaded
  - no_existing_stable_image_component_available

forbidden_techniques: []

# Image asset bloat

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** LCP, CLS

## What this addresses

This issue type covers cases where a page uses a heavier image asset than necessary, or repeatedly swaps/refetches image assets instead of rendering a stable, sized image component. That can delay visual completion, increase bandwidth, and create layout instability when dimensions are missing or change during load.

The goal is to keep the image request small and predictable, and to reserve the final space up front so the browser can paint without shifting content.

## When to apply / when to skip

**Apply when:**
- A visible image is a likely LCP candidate or sits above the fold
- The current asset is larger than needed for the rendered slot
- The image is being replaced with a different asset during render or interaction
- Width and height are missing, incorrect, or not preserved across variants
- The same visual is being fetched multiple times instead of reused from stable markup

**Skip when:**
- The image is decorative and not part of the critical visual path
- The asset is already appropriately sized and stable in markup
- The issue is actually image decoding, CSS blocking, or font/icon replacement rather than the image asset itself
- The image is inserted only after user interaction and is not part of the initial CWV path
- A stable component already exists and the change would duplicate it rather than improve it

## Recommended approaches

### Use the smallest correctly sized asset for the rendered slot

```html
<!-- Good -->
<picture>
  <source srcset="/content/dam/site/hero-960.avif" type="image/avif">
  <source srcset="/content/dam/site/hero-960.webp" type="image/webp">
  <img
    src="/content/dam/site/hero-960.jpg"
    alt="Hero banner"
    width="960"
    height="540"
    loading="eager"
    fetchpriority="high">
</picture>
```

Choose an asset that matches the actual display size instead of shipping a much larger original. Keeping the dimensions explicit lets the browser reserve space and avoids CLS while the image loads.

### Reuse a stable image component instead of swapping raw assets

```html
<!-- Good -->
<sly data-sly-use.image="com.adobe.cq.wcm.core.components.models.Image">
  <img
    src="${image.src}"
    alt="${image.alt}"
    width="${image.width}"
    height="${image.height}"
    loading="eager"
    fetchpriority="high">
</sly>
```

A stable image component centralizes sizing, alt text, and source selection. That reduces the chance of repeated refetches or inconsistent dimensions across templates.

### EDS: keep the image markup stable in the block

```javascript
export default function decorate(block) {
  const img = block.querySelector('img');
  if (!img) return;

  img.loading = 'eager';
  img.fetchPriority = 'high';
  if (!img.width || !img.height) {
    img.width = 960;
    img.height = 540;
  }
}
```

When the image is already in the block markup, preserve it and improve its loading behavior rather than replacing it with a new asset during decoration.

## Anti-patterns

### Replacing a stable image with a heavier asset

```html
<!-- Bad -->
<img src="/content/dam/site/hero-original-4000.jpg" alt="Hero">
```

**Why this is bad:** Shipping a much larger asset than needed can waste bytes and delay the first meaningful paint.

### Swapping image sources during render

```javascript
// Bad
const img = document.querySelector('.hero img');
img.src = '/content/dam/site/hero-large.jpg';
setTimeout(() => {
  img.src = '/content/dam/site/hero-large-v2.jpg';
}, 100);
```

**Why this is bad:** Replacing the source can cause extra fetches and can reset the browser’s loading work, which can hurt LCP and make the visual result less stable.

### Omitting dimensions on a visible image

```html
<!-- Bad -->
<img src="/content/dam/site/card.jpg" alt="Card image">
```

**Why this is bad:** Without width and height, the browser cannot reserve the final space, so the page can shift when the image arrives.

### Using a JS loader to inject the image late

```javascript
// Bad
const hero = document.createElement('img');
hero.src = '/content/dam/site/hero.jpg';
document.querySelector('.hero-slot').appendChild(hero);
```

**Why this is bad:** Late DOM insertion can delay discovery and push the image out of the critical rendering path, especially for above-the-fold content.

## Flavor-specific notes

### EDS

Prefer keeping the authored image in the block HTML and adjusting its attributes in `decorate(block)` only when needed. If the block already has a responsive image helper, use it rather than introducing a second fetch path.

### CS

Use the image component or Adaptive Image Servlet output where available, and keep width/height aligned with the authored component policy. If a template currently hardcodes a DAM original, replace it with the component’s rendered output so the publish tier can serve a sized rendition.

### AMS

Check the JSP or HTL output path before changing the asset reference. Legacy templates often have multiple include layers, so make sure the visible image is not being rendered twice or replaced by a later include.

### Headless

This usually shows up in the client app rather than the CMS layer. Keep the image URL stable, avoid swapping to a larger fallback after hydration, and ensure the rendered slot has explicit dimensions or aspect-ratio reservation.