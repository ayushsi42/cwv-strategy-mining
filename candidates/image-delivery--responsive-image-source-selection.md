---
issue_type: image-delivery--responsive-image-source-selection
parent_strategy: image-delivery
risk_tier: low
cwv_metrics: [performance]
source_prs:
  - aafre/resume-builder#377
  - adobecom/express-milo#770
  - ryanofarrell/playful-progressions#97
  - sprint-19-part4-1team/global-nomad#292
required_validation:
  - responsive_image_has_explicit_sizes_and_dimensions
  - responsive_image_uses_priority_for_likely_lcp
  - responsive_image_source_set_matches_served_variants
forbidden_techniques: []
---

# Responsive image source selection

> **Risk tier:** low · **Parent strategy:** image-delivery · **CWV metric:** performance

## What this addresses

This strategy improves image delivery by matching the served image source to the rendered slot size and, when the image is a likely above-the-fold or LCP candidate, requesting it earlier.

The evidence supports two distinct mechanisms:

1. **Responsive source selection**
   - Provide explicit `sizes` and a variant set that matches the rendered slot.
   - Use smaller variants for smaller slots and larger variants for larger display contexts.
   - Serve pre-generated preview images from a CDN when the asset set is immutable and already available in multiple sizes.

2. **Priority loading for likely LCP imagery**
   - Apply `priority` or `fetchpriority="high"` and eager loading to the first meaningful hero/teaser image when it is the likely LCP element.
   - Keep image dimensions explicit so layout can be reserved while the browser fetches the asset.

## Apply / Skip

### Apply when
- The page renders a hero, teaser, preview, or detail image that is visible early and is a plausible LCP candidate.
- The image is available in multiple generated sizes or formats.
- The rendered image slot is known well enough to define `sizes`.
- The image is served from a stable URL set, such as generated preview assets or CDN-hosted variants.

### Skip when
- The image is decorative, non-critical, or not part of the above-the-fold experience.
- There is no evidence-backed variant set to map to `srcset` and `sizes`.
- The image is not a likely LCP candidate, so priority loading is not justified by the evidence.
- The source cannot be paired with explicit dimensions or variant URLs.

## Required validation

### `responsive_image_has_explicit_sizes_and_dimensions`

**Observed evidence**
- `global-nomad#292` adds `sizes` to a responsive image grid and uses `fill` inside a container with explicit height/width classes.
- `ryanofarrell/playful-progressions#97` adds a `<picture>`/`<img>` setup with `sizes` and multiple width variants.
- `adobecom/express-milo#770` adds `width` and `height` to several image elements, including hero, thumbnail, and icon images.

**What this validation means**
- The rendered image element has explicit sizing information appropriate to the implementation shape:
  - either `sizes` plus responsive variants, or
  - explicit `width` and `height` when the image is not using a responsive fill pattern.
- The layout reserves space for the image so the browser does not need late intrinsic sizing to avoid layout shift.

### `responsive_image_uses_priority_for_likely_lcp`

**Observed evidence**
- `global-nomad#292` sets `priority={index === 0 && (count === 1 || count === 3)}` for the first image in layouts treated as likely LCP candidates.
- `ryanofarrell/playful-progressions#97` uses `loading="eager"` and `fetchpriority="high"` on the teaser image.

**What this validation means**
- The image is the likely first meaningful or hero image for the page.
- The implementation marks that image for early fetch using the mechanism supported by the markup or component shape in the evidence.
- Priority is applied selectively, not to every image in a gallery or thumbnail set.

### `responsive_image_source_set_matches_served_variants`

**Observed evidence**
- `ryanofarrell/playful-progressions#97` serves `400w`, `800w`, and `1600w` variants through `srcset` and `picture` sources for AVIF/WebP.
- `global-nomad#292` uses `sizes` values that correspond to the rendered grid slots.
- `docs/templates/PREVIEW-IMAGES.md` describes generated preview images as `800px` desktop and `400px` mobile variants served from CDN.

**What this validation means**
- The source list corresponds to actual generated or served variants.
- The `sizes` string reflects the intended rendered slot sizes.
- The selected source family is consistent with the asset pipeline described by the evidence.

## Good examples

### Responsive grid image with explicit slot sizing and selective priority

```tsx
<Image
  src={image.imageUrl}
  alt={`체험 상세 이미지 ${index}`}
  fill
  sizes="(max-width: 640px) 161px, (max-width: 1024px) 336px, 329px"
  className="object-cover"
  priority={index === 0 && (count === 1 || count === 3)}
/>
```

**Why this is evidence-aligned**
- Uses explicit `sizes`.
- Matches the rendered slot with responsive selection.
- Applies priority only to the first image when the layout makes it a likely LCP candidate.

### Picture element with width-based variants and early fetch for the teaser image

```html
<picture>
  <source
    srcset="/images/example-400.avif 400w, /images/example-800.avif 800w, /images/example.avif 1600w"
    sizes="(max-width: 575px) 100vw, (max-width: 767px) 540px, (max-width: 991px) 720px, (max-width: 1199px) 800px, 950px"
    type="image/avif">
  <source
    srcset="/images/example-400.webp 400w, /images/example-800.webp 800w, /images/example.webp 1600w"
    sizes="(max-width: 575px) 100vw, (max-width: 767px) 540px, (max-width: 991px) 720px, (max-width: 1199px) 800px, 950px"
    type="image/webp">
  <img
    src="/images/example.jpg"
    srcset="/images/example-400.jpg 400w, /images/example-800.jpg 800w, /images/example.jpg 1600w"
    sizes="(max-width: 575px) 100vw, (max-width: 767px) 540px, (max-width: 991px) 720px, (max-width: 1199px) 800px, 950px"
    loading="eager"
    fetchpriority="high"
    alt="Example preview">
</picture>
```

**Why this is evidence-aligned**
- Uses actual width-based variants.
- Lets the browser choose among format sources.
- Marks the likely LCP teaser image for early fetch.

### CDN-hosted preview images with documented variant sizes

From `docs/templates/PREVIEW-IMAGES.md`:

- `{slug}.webp` — 800px wide desktop variant
- `{slug}-sm.webp` — 400px wide mobile variant

**Why this is evidence-aligned**
- The asset pipeline explicitly produces multiple sizes.
- The delivery path is stable and CDN-backed.
- The variant set is suitable for responsive source selection.

## Anti-patterns

Evidence is insufficient to define a defensible pre-change anti-pattern for this child strategy. The supplied patches show positive responsive-image and priority-loading changes, but not a validated regression example for this exact mechanism.

## How to verify

Use the same measurement family already associated with this strategy: **performance**.

### Verification steps
1. Load the page before and after the change.
2. Confirm the intended image renders in the expected slot.
3. Inspect the image request pattern:
   - the browser should select a source that matches the rendered slot size,
   - the responsive variant set should correspond to the documented asset sizes,
   - and the likely LCP image should be the one receiving priority/eager treatment when applicable.
4. Compare the performance metric before and after the change.

### Verification criteria
- The image request resolves to the expected variant for the viewport.
- The image element includes explicit sizing information.
- The likely LCP image is prioritized only when it is actually the first meaningful image.
- The performance measurement is recorded before and after; do not claim a fixed improvement without a measured result.

## Evidence and confidence

### Observed facts
- `global-nomad#292` introduces a responsive image grid using `next/image`, explicit `sizes`, and selective `priority` on the first image for 1- and 3-image layouts.
- `ryanofarrell/playful-progressions#97` replaces a single teaser image with a `<picture>` element using AVIF/WebP sources, width-based `srcset`, `sizes`, and eager/high-priority loading.
- `docs/templates/PREVIEW-IMAGES.md` documents generated preview images with 400px and 800px variants served from a CDN.
- `adobecom/express-milo#770` adds explicit dimensions and image metadata to several image elements, including a hero image and thumbnails.

### Inference
- These changes support a general strategy of matching image source selection to rendered slot size and prioritizing the likely LCP image when the image is above the fold.
- The evidence supports this as a low-risk performance optimization because it changes image delivery shape rather than page structure or business logic.

### Confidence
- Medium for the general mechanism.
- Higher confidence for the specific conditions where the image is a known hero, teaser, or LCP candidate and the variant set is already available.

## Risks and limitations

- Priority loading should be reserved for the likely LCP image; applying it broadly to many images is not evidence-backed here.
- Responsive source selection depends on having real variant assets and a `sizes` string that matches the rendered slot.
- If the image is not actually visible early, the optimization may not help performance.
- The evidence does not justify universal browser support claims, universal byte-reduction percentages, or a fixed CWV delta.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (4 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **5 observations across 5 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: image-delivery--responsive-image-source-selection`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
