---
issue_type: image-delivery--lazy-load-non-critical-images-by-default
parent_strategy: image-delivery
risk_tier: low
cwv_metrics:
  - Lighthouse performance
  - Lighthouse performance / image loading
  - Lighthouse LCP / image loading
  - Lighthouse performance / offscreen images
  - perf_flagged
  - Lighthouse LCP / CLS / performance review
source_prs:
  - teetee971/akiprisaye-web#2110
  - AcademiahubAfrica/Academiahub#416
  - opengovsg/isomer#1574
  - ericabertugli/ericabertugli.github.io#22
  - komalharshita/DevPath#102
required_validation:
  - non_critical_image_has_intrinsic_dimensions
  - non_critical_image_uses_lazy_loading
  - critical_above_fold_image_remains_eager
forbidden_techniques: []
---
# Lazy-load non-critical images by default

> **Risk tier:** low · **Parent strategy:** image-delivery · **CWV metrics:** Lighthouse performance / image loading, Lighthouse performance / offscreen images, Lighthouse LCP / image loading, Lighthouse LCP / CLS / performance review

## What this addresses

This strategy applies to images that are not needed for the initial viewport. The evidence supports two coordinated changes for those images:

1. Add intrinsic dimensions so the browser can reserve layout space before the image decodes.
2. Add lazy loading so offscreen images are fetched and decoded only when needed.

This is an image-delivery tactic, not a universal rule for every image. The supplied evidence also shows that critical above-the-fold images should remain eager and may be explicitly prioritized instead of being converted to lazy loading.

## Apply / skip gates

### Apply when
- The image is not required for the initial render.
- The image is below the fold, offscreen, decorative, or otherwise non-critical.
- The image appears in a repeated list, card, grid, or thumbnail pattern.
- The image is rendered with a plain `<img>` or an image abstraction that accepts sizing and loading props.
- You can determine a stable rendered size or aspect ratio.

### Skip when
- The image is part of the initial viewport and is important to LCP or first paint.
- The image is intentionally prioritized for immediate loading.
- The image is already handled by a separate critical-image strategy.
- The rendered size cannot be stated reliably.

## Required validations

### `non_critical_image_has_intrinsic_dimensions`
**What it checks:** non-critical images declare a stable size contract before decode.

**Pass condition:**
- The image has explicit `width` and `height` attributes, or an equivalent stable sizing contract in the markup.
- The declared dimensions match the intended rendered box or aspect ratio.

**Evidence-derived examples:**
- `width={56} height={56}` on small product images.
- `width={600} height={208}` on a product header image.
- `width={128} height={128}` on a QR code.
- `width={200} height={24}` on a barcode image.
- `width={288} height={162}` on a promo image.

**Why it matters:** intrinsic dimensions let the browser reserve space before decode, which reduces layout instability risk.

---

### `non_critical_image_uses_lazy_loading`
**What it checks:** non-critical images are marked to defer loading until needed.

**Pass condition:**
- The image includes `loading="lazy"`.
- The image is not part of the initial critical render.

**Evidence-derived examples:**
- Product images in comparison and scanner views.
- Promo imagery in a home carousel.
- Decorative or supporting images in static pages.
- Repeated child-page thumbnails when lazy loading is passed through a wrapper.

**Why it matters:** lazy loading defers offscreen image downloads and decoding until the image is needed.

---

### `critical_above_fold_image_remains_eager`
**What it checks:** critical above-the-fold images are not downgraded to lazy loading.

**Pass condition:**
- The image remains eager when it is part of the initial viewport and important to LCP.
- If the implementation supports it, the image may also be explicitly prioritized.

**Evidence-derived example:**
- A hero image is kept eager with `loading="eager"` and `fetchPriority="high"`.

**Why it matters:** this prevents applying the non-critical-image rule to a critical asset.

## Recommended implementation patterns

### 1) Add intrinsic dimensions and lazy loading to non-critical `<img>` elements

This is the clearest pattern in the evidence.

```tsx
Good
<img
  src={productImage}
  alt="produit"
  className="w-14 h-14 object-contain rounded bg-white"
  width={56}
  height={56}
  loading="lazy"
/>
```

**Evidence basis:** small product images were updated with both dimensions and `loading="lazy"`.

**Expected effect:** the browser can reserve space and defer offscreen work.

---

### 2) Thread lazy loading through reusable image wrappers

When a layout renders repeated thumbnails or child-page images, pass the loading decision through the wrapper instead of hard-coding it at one call site.

```tsx
Good
<ChildpageImage
  assetsBaseUrl={assetsBaseUrl}
  lazyLoading={shouldLazyLoad}
  {...renderedImage}
  className={styles.image({ hasFallbackImage: !image?.src })}
/>
```

**Evidence basis:** the child-page image abstraction was extended with a `shouldLazyLoad`/`lazyLoading` path.

**Expected effect:** the layout can decide whether images are non-critical while the rendering component stays reusable.

---

### 3) Keep critical hero images eager and prioritized

Do not convert a critical above-the-fold image to lazy loading.

```tsx
Good
<Image
  className="w-full h-auto lg:rounded-l-2xl"
  src={HeroImg}
  alt="Hero image"
  width={704}
  height={651}
  loading="eager"
  fetchPriority="high"
/>
```

**Evidence basis:** the hero image in the supplied evidence was kept eager and explicitly prioritized.

**Expected effect:** the initial viewport image remains available as early as possible.

## Bad examples

### Bad: lazy-loading a critical hero image
```tsx
Bad
<img
  src={image}
  alt={name}
  className="h-full w-full object-cover"
  loading="lazy"
/>
```

**Why this is bad:** the evidence distinguishes non-critical images from critical hero imagery. Lazy loading is appropriate for non-critical images, but not for an image that is part of the initial viewport and important to LCP.

---

### Bad: lazy-loading without a stable size contract
```tsx
Bad
<img src={promo.img} className="absolute inset-0 w-full h-full object-cover opacity-50" alt="" loading="lazy" />
```

**Why this is bad:** the evidence pairs lazy loading with explicit dimensions on non-critical images. If the rendered size is known, declare it so the browser can reserve space before decode.

## Verification

Use measurable checks tied to the supplied CWV signals:

1. **Lighthouse performance / image loading**
   - Confirm fewer non-critical images are loaded eagerly.
   - Confirm offscreen images are deferred.

2. **Lighthouse performance / offscreen images**
   - Verify offscreen image requests are reduced or delayed.

3. **Lighthouse LCP / image loading**
   - Confirm critical images are not accidentally converted to lazy loading.

4. **Lighthouse LCP / CLS / performance review**
   - Confirm intrinsic dimensions reduce layout instability risk.

### Practical pass criteria
- Non-critical images have explicit dimensions and `loading="lazy"`.
- Critical above-the-fold images remain eager.
- No new layout shift is introduced by image loading changes.
- The image-loading audit shows fewer unnecessary eager image fetches.

## Evidence summary

### Observed facts
- Multiple repositories added `loading="lazy"` to non-critical images.
- Multiple repositories added explicit `width` and `height` attributes to those same images.
- One repository passed lazy-loading through a reusable child-page image abstraction.
- One repository kept a hero image eager and explicitly prioritized with `fetchPriority="high"`.
- The supplied observations are directionally consistent: 6 improvements, 0 regressions.

### Inference
- The safest default is to lazy-load non-critical images and to pair that with intrinsic dimensions when the rendered size is known.
- Critical above-the-fold images should remain eager.

### Confidence
- **Medium**
- Statistical support: 6 observations across 6 repositories
- Absolute measured-delta summary: p25=None, median=None, p75=None

## Source PRs
- `teetee971/akiprisaye-web#2110`
- `AcademiahubAfrica/Academiahub#416`
- `opengovsg/isomer#1574`
- `ericabertugli/ericabertugli.github.io#22`
- `komalharshita/DevPath#102`

## Risks and limitations
- Applying lazy loading to a critical above-the-fold image can delay the asset that matters most for LCP.
- Adding lazy loading without intrinsic dimensions can leave layout space unresolved until decode.
- The evidence supports this as a low-risk image-delivery tactic only when image criticality is classified correctly.
- The supplied patches do not justify a universal rule for every image; the apply/skip gates above are required.