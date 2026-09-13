---
issue_type: image-format
applicable_flavors:
- eds
- cs
- ams
risk_tier: medium
required_validation:
- Verify Lighthouse attribution identifies a raster hero image as the LCP element.
- Verify the source asset and selected delivery path can produce the intended WebP
  and fallback renditions.
- Verify responsive rendition widths, crops, and visual quality at representative
  viewport sizes.
- Verify intrinsic image dimensions are retained in rendered markup.
- Verify WebP selection and fallback rendering on representative clients.
forbidden_techniques: []
source_prs:
- woowacourse/perf-basecamp#170
- woowacourse/perf-basecamp#178
- woowacourse/perf-basecamp#161
- adobecom/express-milo#770
- 0-sayed/hena-wadeena#138
- woowacourse/perf-basecamp#17
- woowacourse/perf-basecamp#39
- u-sho/quantum-game-arena#89
- laws-africa/peachjam#1361
- hlxsites/fonterra-fernleaf#58
- woowacourse/perf-basecamp#81
- woowacourse/perf-basecamp#107
- woowacourse/perf-basecamp#100
- WgtTelia/Telia-e-shop-front-end#11
- woowacourse/perf-basecamp#149
- dailydotdev/apps#3847
- FOSSUChennai/Communities#238
---
# Image format

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS · **CWV metric:** LCP

## What this addresses

Oversized PNG or JPEG hero images can delay download of the primary visual resource, worsening LCP. The evidence shows that converting PNG banners to WebP can reduce file size and improve load performance. Serving appropriately sized WebP renditions with a fallback can reduce transferred bytes while preserving the authored image and visual quality.

## When to apply / when to skip
**Apply when:**
- Lighthouse identifies a raster hero `<img>` as the LCP element and the delivered PNG or JPEG is materially larger than a verified WebP rendition.
- The image delivery path can serve or reference verified WebP and fallback renditions.
- Responsive renditions preserve the intended crop and visual quality at each rendered breakpoint.
- The component can retain stable `width` and `height` values while changing the delivered source format.

### When to skip

- The LCP element is text, video, SVG, or a CSS background rather than a raster image.
- The existing image delivery service already selects an appropriately sized modern rendition for the audited viewport.
- The asset contains transparency, gradients, fine text, or legal or product-detail content that has not been visually approved after conversion.
- The source image is injected by JavaScript after initial rendering; changing its format alone may not address the discovery delay.
- Lighthouse shows render delay dominating LCP with **FCP == LCP**; investigate render-blocking CSS or scripts before changing the image format.

## Recommended approaches

### EDS: use responsive image output from block markup

Use the site’s established image helper or delivery mechanism when converting a hero block's authored image into responsive output. Preserve a fallback `<img>` and verify that the rendered markup selects appropriate image resources.

**Good:**

```javascript
// blocks/hero/hero.js
import { createOptimizedPicture } from '../../scripts/aem.js';

export default function decorate(block) {
  const authoredImage = block.querySelector('picture img');
  if (!authoredImage) return;

  const optimizedPicture = createOptimizedPicture(
    authoredImage.src,
    authoredImage.alt,
    true,
    [{ width: '768' }, { width: '1200' }, { width: '1600' }],
  );

  const heroImage = optimizedPicture.querySelector('img');
  heroImage.setAttribute('fetchpriority', 'high');
  heroImage.setAttribute('loading', 'eager');
  heroImage.setAttribute('width', authoredImage.getAttribute('width') || '1600');
  heroImage.setAttribute('height', authoredImage.getAttribute('height') || '900');

  authoredImage.closest('picture').replaceWith(optimizedPicture);
}
```

Verify that the resulting markup requests an image close to the rendered slot size rather than the full authored original. Preserve a fallback `<img>` and verify its behavior in the supported client set. See [`lcp-image.md`](./lcp-image.md) for LCP priority attributes and [`image-sizing.md`](./image-sizing.md) for dimension reservation.

### CS/AMS: render verified delivery-service renditions with WebP and a fallback image

Expose verified rendition URLs from the image component rather than hardcoding a single original DAM asset in HTL. Use the same approved crop and aspect ratio for each width candidate.

**Good:**

```html
<!-- /apps/site/components/hero/hero.html -->
<sly data-sly-use.hero="com.site.core.models.HeroImage" />

<picture data-sly-test="${hero.hasImage}">
  <source type="image/webp"
          srcset="${hero.webp768} 768w,
                  ${hero.webp1200} 1200w,
                  ${hero.webp1600} 1600w"
          sizes="(max-width: 767px) 100vw, 1200px">

  <img class="cmp-hero__image"
       src="${hero.jpeg1200}"
       width="${hero.width}"
       height="${hero.height}"
       alt="${hero.alt}"
       loading="eager"
       fetchpriority="high">
</picture>
```

Use only rendition URLs known to be generated by the DAM, image service, or approved project delivery path. The fallback image provides an alternate source where WebP is not used.

### Match rendition widths to the rendered hero slot

Keep each `srcset` candidate at the same approved crop and use `sizes` to describe the actual layout width. This allows the browser to select a width-specific candidate rather than always using the largest rendition.

**Good:**

```html
<!-- Each candidate uses the same approved hero crop. -->
<picture>
  <source type="image/webp"
          srcset="/content/dam/site/hero/launch-768.webp 768w,
                  /content/dam/site/hero/launch-1200.webp 1200w,
                  /content/dam/site/hero/launch-1600.webp 1600w"
          sizes="(max-width: 767px) 100vw, (max-width: 1279px) 90vw, 1200px">
  <img src="/content/dam/site/hero/launch-1200.jpg"
       width="1600"
       height="900"
       alt="Product launch collection"
       loading="eager"
       fetchpriority="high">
</picture>
```

Validate the selected source and transferred bytes at representative viewport widths. Evidence includes responsive `srcset` examples using 770px and 1920px candidates and reports smaller mobile and desktop hero assets after optimization.

## Anti-patterns

### Serving the authored PNG as every responsive candidate

```html
<!-- Bad: every viewport receives the same oversized legacy source. -->
<img class="cmp-hero__image"
     src="/content/dam/site/hero/summer-campaign.png"
     srcset="/content/dam/site/hero/summer-campaign.png 768w,
             /content/dam/site/hero/summer-campaign.png 1200w,
             /content/dam/site/hero/summer-campaign.png 1600w"
     sizes="100vw"
     alt="Summer campaign">
```

**Why this is bad:** Labeling one PNG with multiple widths does not produce width-specific or WebP renditions. Clients can still receive the same oversized PNG.

### Providing WebP without a fallback image

```html
<!-- Bad: the picture contains only a WebP source. -->
<picture>
  <source type="image/webp"
          srcset="/content/dam/site/hero/summer-1200.webp 1200w">
</picture>
```

**Why this is bad:** This markup does not include an `<img>` fallback or intrinsic dimensions. Include a fallback `<img>` and verify rendering in the supported client set.

### Changing format without checking the delivered crop and quality

```html
<!-- Bad: an arbitrary low-quality rendition changes the approved composition. -->
<img src="/content/dam/site/hero/summer-hero.webp"
     width="1600"
     height="900"
     alt="Summer campaign"
     loading="eager">
```

**Why this is bad:** The evidence supports resizing and compression only when the resulting image remains acceptable. Verify crop, aspect ratio, and visual quality before replacing an approved hero asset.

## Flavor-specific notes

### EDS

Use the hero block’s established image-output mechanism rather than manually constructing unverified image-delivery query strings. Confirm that the configured delivery endpoint returns the expected rendition for the authored asset and that the resulting `<img>` preserves intrinsic dimensions.

Do not defer the above-the-fold hero without measuring the effect on LCP. Verify the rendered request priority and load behavior for the audited page.

### CS

Prefer the project’s approved image-delivery integration for rendition generation rather than committing duplicate converted binaries without a managed rendition process. Trace the hero component model and its page-template usage before changing source selection, because a shared image component may also render non-LCP cards and editorial images.

Verify the publish URL, dispatcher cache behavior, and content policy configuration for each generated rendition. A rendition that works on author but is blocked, uncached, or rewritten incorrectly on publish will not provide the intended delivery improvement.

### AMS

Identify the image component’s `sling:resourceType` and output path before assuming a particular image-service capability. AMS projects may use custom image servlets or static DAM renditions; use only formats and width parameters that the existing publish and dispatcher path demonstrably serves.

If the project maintains static DAM renditions, have authors or the DAM workflow generate WebP and fallback assets together from the same approved crop. Do not point production hero markup at a rendition path until it has been verified on publish with the expected content type and dimensions.