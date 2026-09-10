---
issue_type: legacy-image-encoding
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation: []
forbidden_techniques:
- pattern: '[''"]react-multi-carousel[''"]'
  reason: Do not add a carousel dependency solely to present converted images unless
    its bundle impact is measured alongside image-byte savings.
source_prs:
- lifeisbeautifu1/modern-react-app#47
- jarobase/loficode-hugo-theme#2
- 0-sayed/hena-wadeena#138
- estartando-devs/site#117
- woowacourse/perf-basecamp#60
- u-sho/quantum-game-arena#89
- withastro/astro.build#562
- jbx-protocol/juice-interface#3529
- woowacourse/perf-basecamp#70
- solo-io/dev-portal-starter#92
- woowacourse/perf-basecamp#137
- move-fast-and-break-things/mfbt.community#59
- FOSSUChennai/Communities#238
---
# Legacy image encoding

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** LCP

## What this addresses

PNG assets can be converted to WebP as part of image-size and Lighthouse performance work. Evidence PRs used WebP conversion and, in one case, `<picture>` markup with WebP sources.

## When to apply / when to skip
**Apply when:**
- Lighthouse, a network trace, or an image-byte inventory identifies a large PNG requested by the audited page.
- The asset's rendered use is known, including whether it is static, animated, above the fold, or the LCP element.
- A WebP replacement has been visually compared at the rendered dimensions used by the page.
- The component has a fallback path where the site's browser-support policy requires one.

**Skip when:**
- The candidate is a small UI icon, favicon, transparent brand mark, or pixel-art asset for which conversion provides no measured transfer benefit or degrades appearance.
- The PNG's alpha channel, color profile, or editorial detail is visibly degraded by conversion.
- The changed asset URL cannot be traced through DAM, EDS content, or the headless frontend's content model.

## Recommended approaches

### Serve a WebP source with a retained fallback

Use `<picture>` when the delivery layer needs explicit format negotiation. Keep the fallback image so browsers or downstream consumers that do not support WebP can still render the visual.

```html
<!-- WebP is preferred, while the original JPEG remains a fallback -->
<picture>
  <source type="image/webp"
          srcset="/content/dam/site/hero/market-1200.webp 1200w,
                  /content/dam/site/hero/market-800.webp 800w"
          sizes="(max-width: 767px) 100vw, 1200px">
  <img src="/content/dam/site/hero/market-1200.jpg"
       srcset="/content/dam/site/hero/market-1200.jpg 1200w,
               /content/dam/site/hero/market-800.jpg 800w"
       sizes="(max-width: 767px) 100vw, 1200px"
       width="1200"
       height="800"
       alt="Farmers harvesting dates">
</picture>
```

### EDS: replace a non-critical block image with optimized WebP markup

For a below-the-fold EDS block, defer decorative image loading until the block approaches the viewport.

```javascript
// blocks/promo/promo.js
import { buildPromoPicture } from './promo-media.js';

export default function decorate(block) {
  const observer = new IntersectionObserver((entries) => {
    if (!entries[0].isIntersecting) return;

    const picture = buildPromoPicture({
      webp: '/media_1234567890abcdef.webp',
      fallback: '/media_1234567890abcdef.png',
      alt: 'Seasonal offers',
      width: 960,
      height: 540,
    });

    block.append(picture);
    observer.disconnect();
  }, { rootMargin: '300px 0px' });

  observer.observe(block);
}
```

```javascript
// blocks/promo/promo-media.js
export function buildPromoPicture({ webp, fallback, alt, width, height }) {
  const picture = document.createElement('picture');
  const source = document.createElement('source');
  const image = document.createElement('img');

  source.type = 'image/webp';
  source.srcset = webp;
  image.src = fallback;
  image.alt = alt;
  image.width = width;
  image.height = height;
  image.loading = 'lazy';

  picture.append(source, image);
  return picture;
}
```

## Anti-patterns

### Replacing a PNG URL without responsive sources or a fallback

```html
<!-- One converted file is used for every viewport and browser -->
<img src="/content/dam/site/hero/market-2400.webp"
     alt="Farmers harvesting dates">
```

**Why this is bad:** This does not provide a fallback where the supported browser matrix requires one.

### Lazy-loading an above-the-fold converted image

```html
<!-- The hero was converted, but its request is deferred -->
<picture>
  <source type="image/webp" srcset="/content/dam/site/hero/market.webp">
  <img src="/content/dam/site/hero/market.png"
       alt="Farmers harvesting dates"
       loading="lazy"
       width="1200"
       height="800">
</picture>
```

**Why this is bad:** Verify this behavior in the audited page rather than assuming that conversion alone resolves the LCP issue.

### Treating an animated GIF as a static WebP

```html
<!-- The original conveyed a multi-step process, but conversion removes it -->
<img src="/content/dam/site/promo/checkout-steps.webp"
     alt="Checkout process">
```

**Why this is bad:** Confirm that the converted asset still represents the required content.

### Adding carousel code solely to present converted media

```html
<!-- Carousel controls and slide structure were added only for converted media -->
<section class="promo-carousel" aria-label="Seasonal offers">
  <button type="button" class="promo-carousel__previous" aria-label="Previous offer">
    Previous
  </button>

  <div class="promo-carousel__slides">
    <picture class="promo-carousel__slide">
      <source type="image/webp" srcset="/content/dam/site/promo/offer.webp">
      <img src="/content/dam/site/promo/offer.png"
           alt="Seasonal offer"
           width="960"
           height="540">
    </picture>
  </div>

  <button type="button" class="promo-carousel__next" aria-label="Next offer">
    Next
  </button>
</section>
```

**Why this is bad:** Measure the bundle impact of the added dependency alongside the image-byte savings.