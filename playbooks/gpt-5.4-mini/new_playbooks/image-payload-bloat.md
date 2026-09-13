---
issue_type: image-payload-bloat
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: low
required_validation:
- image_format_swap_confirmed
- source_asset_is_browser_facing
- no_existing_modern_format_delivery
- responsive_variant_path_known
forbidden_techniques: []
source_prs:
- team-prstmw/StarWarsQuiz#5
- estartando-devs/site#117
- u-sho/quantum-game-arena#89
- vazco/forminer#42
- TTG-Club/ttg-club-frontend#217
- solo-io/dev-portal-starter#92
- woowacourse/perf-basecamp#132
- move-fast-and-break-things/mfbt.community#59
- stephanieran/personal-portfolio#13
- SOPT-all/35-APPJAM-WEB-DASH#335
- NativePHP/nativephp.com#89
---
# Image payload bloat

> **Risk tier:** low · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** LCP, INP, overall load performance

## What this addresses

Large PNG, GIF, or unoptimized JPEG assets can dominate network transfer and delay the first meaningful paint of key content. Replacing them with modern formats like WebP or AVIF, and serving appropriately sized variants, can reduce payload size and improve LCP and overall page load performance.

## When to apply / when to skip
**Apply when:**
- The audited asset is browser-facing and contributes to above-the-fold rendering or a visible interaction
- The current asset is a large PNG, GIF, or oversized raster image
- A smaller modern format is available or can be generated without changing the visual intent
- The page can serve a responsive or format-converted variant for the same visual slot

**Skip when:**
- The asset is already delivered in an efficient modern format at the right dimensions
- The issue is not payload size but render blocking, layout shift, or lazy-loading behavior
- The image is a brand-critical raster that must remain lossless and the size is already acceptable
- The media is not an image/video payload problem at all, but a CSS/JS or server-side bottleneck

## Recommended approaches

### Use `<picture>` with modern format first and fallback second

```html
<!-- Good: modern format first, fallback second -->
<picture>
  <source srcset="/images/hero.avif" type="image/avif">
  <source srcset="/images/hero.webp" type="image/webp">
  <img
    src="/images/hero.png"
    alt="Hero banner"
    width="1200"
    height="800"
    loading="eager"
    decoding="async">
</picture>
```

This lets capable browsers fetch the smaller AVIF/WebP asset while preserving compatibility with a fallback image. Keeping explicit dimensions also helps reserve space and avoid CLS.

### Serve responsive variants for large raster images

```html
<!-- Good: right-size the payload for the viewport -->
<img
  src="/images/gallery-960.webp"
  srcset="/images/gallery-480.webp 480w,
          /images/gallery-960.webp 960w,
          /images/gallery-1440.webp 1440w"
  sizes="(max-width: 768px) 100vw, 50vw"
  alt="Gallery preview"
  width="960"
  height="640"
  loading="lazy"
  decoding="async">
```

Responsive delivery avoids shipping a desktop-sized image to mobile users. The browser picks the smallest acceptable candidate for the current viewport and DPR.

### Convert animated GIFs to WebM or another efficient video format

```html
<!-- Good: replace heavy GIF animation with a video -->
<video
  autoplay
  muted
  loop
  playsinline
  width="640"
  height="360"
  poster="/media/animation-poster.webp">
  <source src="/media/animation.webm" type="video/webm">
  <source src="/media/animation.mp4" type="video/mp4">
</video>
```

For looping decorative motion, video formats are usually far smaller than GIF and decode more efficiently in the browser.

## Anti-patterns

### Shipping a large PNG when a modern format is available

```html
<!-- Bad -->
<img src="/images/hero.png" alt="Hero banner" width="1200" height="800">
```

**Why this is bad:** PNG can carry a larger payload than WebP or AVIF for photographic or complex imagery, which can increase transfer time and delay LCP.

### Using GIF for decorative animation

```html
<!-- Bad -->
<img src="/media/loader.gif" alt="Loading animation">
```

**Why this is bad:** GIF is typically much larger than WebM or MP4 for motion content and can waste bandwidth and decode time on every view.

### Upscaling a tiny asset in CSS

```css
/* Bad */
.hero {
  background-image: url('/images/hero-400.png');
  background-size: cover;
  width: 1200px;
  height: 800px;
}
```

**Why this is bad:** The browser still downloads the small source asset, then stretches it to fill a much larger slot, which can look blurry and still fail to optimize payload for the actual display size.

### Re-encoding without changing delivery size or format

```html
<!-- Bad -->
<img src="/images/banner.jpg" alt="Banner" width="2400" height="1600">
```

**Why this is bad:** Recompressing the same oversized format without serving a smaller modern variant or responsive source set leaves the network cost largely unchanged.

## Flavor-specific notes

### EDS

Prefer block markup that emits `<picture>` or a responsive `<img srcset>` directly from the block. If the asset is authored in a document or fetched from a content source, keep the conversion logic close to the block so the browser receives the optimized variant in the rendered HTML.

```javascript
export default function decorate(block) {
  block.innerHTML = `
    <picture>
      <source srcset="/images/hero.avif" type="image/avif">
      <source srcset="/images/hero.webp" type="image/webp">
      <img src="/images/hero.png" alt="Hero banner" width="1200" height="800">
    </picture>
  `;
}
```

### CS

Use the image component or template markup to emit modern formats and responsive renditions. If the site uses the Adaptive Image Servlet or a similar delivery path, point the component at the optimized rendition rather than the authored original.

```html
<!-- Good: template/component markup -->
<picture>
  <source srcset="${image.avifRendition}" type="image/avif">
  <source srcset="${image.webpRendition}" type="image/webp">
  <img src="${image.originalPath}" alt="${image.alt}" width="1200" height="800">
</picture>
```

If the component is backed by a Sling Model, expose rendition URLs from the model instead of hardcoding asset paths in HTL.

### AMS

Prefer component or JSP output that selects optimized renditions from DAM or a custom image servlet. If the legacy stack only serves the original asset, update the rendering path so the page emits a smaller browser-facing variant rather than the source upload.

```jsp
<picture>
  <source srcset="<%= image.getAvifUrl() %>" type="image/avif" />
  <source srcset="<%= image.getWebpUrl() %>" type="image/webp" />
  <img src="<%= image.getOriginalUrl() %>" alt="<%= image.getAlt() %>" width="1200" height="800" />
</picture>
```