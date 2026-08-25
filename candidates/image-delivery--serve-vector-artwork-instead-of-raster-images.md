---
issue_type: image-delivery--serve-vector-artwork-instead-of-raster-images
parent_strategy: image-delivery
risk_tier: low
cwv_metrics:
  - LCP
  - Lighthouse LCP / image payload
  - Lighthouse image payload / LCP image
  - image payload reduction
source_prs:
  - incubator-social/vopp.me#48
  - find-my-item/FMI-FE#419
  - Molecule-AI/landingpage#27
  - arii/tech-dancer#2379
required_validation:
  - vector_artwork_is_simple_illustration_or_logo
  - raster_asset_is_replaced_by_svg_or_equivalent_vector_source
  - image_is_used_as_static_artwork_not_photographic_content
forbidden_techniques: []
---

# Serve vector artwork instead of raster images

> **Risk tier:** low · **Parent strategy:** image-delivery · **CWV metric:** LCP

## What this addresses

This strategy applies when a page uses a raster image for simple static artwork and a vector source can represent the same visual more efficiently.

The supplied evidence shows the same substitution pattern across four repositories:

- raster artwork replaced with SVG
- the image role remains static UI artwork, branding, or placeholder content
- the page ships fewer raster bytes and avoids raster decoding/scaling work for that artwork

The evidence supports this for logos, profile placeholders, verification illustrations, and other simple hero-style artwork. It does not support applying the strategy to photographs.

## Apply / skip gates

### Apply when all are true
- The asset is simple artwork, not a photograph.
- The visual can be represented faithfully as SVG or another vector source.
- The image is static UI artwork, branding, or a placeholder/fallback asset.
- The current implementation uses a raster file where a vector file is a valid replacement.

### Skip when any are true
- The asset is photographic or depends on photographic detail.
- The asset is already vector-based.
- The image is not part of the page’s meaningful image payload.
- The replacement would require a new rendering behavior not supported by the evidence.

## Required validation

### `vector_artwork_is_simple_illustration_or_logo`
Confirm the source image is simple artwork suitable for vector representation.

Evidence-derived examples:
- logo mark
- profile placeholder
- email-verification illustration
- static event hero artwork represented as SVG

This validation exists because the evidence only shows successful substitutions for simple artwork, not for photos or complex raster imagery.

### `raster_asset_is_replaced_by_svg_or_equivalent_vector_source`
Confirm the shipped asset changes from raster to SVG, or the component now references an SVG source directly.

Evidence-derived examples:
- `public/logo.png` → `public/logo.svg`
- `public/email-verification-img/success.svg`
- `public/user/default-profile.svg`
- `image: "/assets/events/jjo-hero.svg"`

This validation is about the asset format change itself, not about any framework-specific loading API.

### `image_is_used_as_static_artwork_not_photographic_content`
Confirm the image is used as static UI artwork rather than content that requires photographic fidelity.

Evidence-derived examples:
- header/footer logo
- profile avatar fallback
- email verification illustration
- content hero image represented as vector artwork

This validation prevents overgeneralizing the strategy to photographic assets.

## Recommended approach

Prefer a direct asset substitution when the artwork is already available or can be authored as SVG.

### Good: verification illustration as SVG

Evidence-derived shape from `incubator-social/vopp.me#48`:

```tsx
import SuccessImage from '@/public/email-verification-img/success.svg';

export function EmailVerificationPage() {
  return (
    <div style={{ width: 432, height: 300 }}>
      <SuccessImage width={432} height={300} />
    </div>
  );
}
```

Why this is good:
- the asset is static illustration artwork
- the source is SVG
- the layout gives the image explicit dimensions

### Good: logo served as SVG

Evidence-derived shape from `Molecule-AI/landingpage#27`:

```astro
<img
  src="/logo.svg"
  alt=""
  width="36"
  height="36"
  loading="lazy"
  decoding="async"
/>
```

Why this is good:
- the logo is simple branding artwork
- the raster logo was replaced by SVG
- the markup still serves the same visual role

### Good: fallback avatar as SVG

Evidence-derived shape from `find-my-item/FMI-FE#419`:

```tsx
const FALLBACK_SRC = "/user/default-profile.svg";

<Image
  src={imgSrc}
  alt={`${alt} 프로필`}
  width={size}
  height={size}
  sizes={`${size}px`}
  priority={priority}
  draggable={false}
  onError={() => {
    if (imgSrc !== FALLBACK_SRC) setImgSrc(FALLBACK_SRC);
  }}
/>
```

Why this is good:
- the fallback is a simple placeholder illustration
- the fallback source is SVG
- the component preserves a usable image when no custom source exists

## Bad

The supplied evidence does not include a validated pre-change anti-pattern that can be safely expressed as a universal regex or a specific forbidden code pattern. Use the apply/skip gates above instead of trying to match a generic bad pattern.

## How to verify

Verification should be measurable at the page level.

Check that:

1. The page now serves the vector asset instead of the raster asset.
2. The image is still rendered in the intended UI location.
3. Lighthouse image-related signals improve or remain favorable:
   - LCP
   - Lighthouse LCP / image payload
   - Lighthouse image payload / LCP image
   - image payload reduction

Recommended verification steps:
- Inspect the final asset URL in the rendered page.
- Confirm the asset extension or source is SVG.
- Compare before/after Lighthouse runs for the page.
- Record whether the image payload-related metric decreases.

The evidence does not justify claiming a fixed percentage improvement or a guaranteed LCP gain for every case.

## Evidence

### `incubator-social/vopp.me#48`
Observed change:
- `public/email-verification-img/success.svg` added
- email verification page updated to render SVG artwork
- page layout adjusted around the new illustration

Evidence-derived inference:
- a verification-state illustration was moved to vector artwork
- the change is consistent with reducing image payload for static UI artwork

### `find-my-item/FMI-FE#419`
Observed change:
- `public/user/default-profile.svg` added
- profile rendering switched to a `ProfileAvatar` component
- raster profile rendering was replaced with a default SVG fallback

Evidence-derived inference:
- avatar/placeholder imagery is a valid vector-artwork use case
- the fallback pattern preserves UI behavior while avoiding a raster placeholder

### `Molecule-AI/landingpage#27`
Observed change:
- `public/logo.svg` added
- header and footer references changed from `/logo.png` to `/logo.svg`

Evidence-derived inference:
- logos are a strong fit for vector substitution
- the same branding role can be served with a smaller, resolution-independent asset

### `arii/tech-dancer#2379`
Observed change:
- content metadata and markdown image references changed from `.jpg` to `.svg`
- the hero image path was updated to a vector asset

Evidence-derived inference:
- some hero artwork can be represented as SVG when it is illustration-like rather than photographic
- content-managed image references can also benefit from vector substitution when the artwork is suitable

## Evidence vs inference

### Evidence
- Four repositories independently replaced raster artwork with SVG or direct vector sources.
- The assets were simple static artwork: logos, placeholders, verification art, and illustration-style hero imagery.
- The supplied packet reports consistent directional improvement across the observed changes.

### Inference
- The shared mechanism is not “use SVG everywhere.”
- The shared mechanism is “use vector artwork when the visual is simple static artwork and the vector form is a faithful replacement.”
- The likely CWV benefit is reduced image payload and less raster decoding/scaling work for the artwork that contributes to the page’s image load.

## Risks and limitations

- SVG is appropriate only when the visual content is suitable for vector representation.
- A complex SVG can still be heavy; vector format alone does not guarantee a smaller payload.
- This strategy is about asset choice and delivery shape, not about browser support tricks or client-side image transformation.
- Do not apply it to photographic content unless the evidence for that specific asset supports a faithful vector replacement.

## Confidence

- **Confidence:** medium
- **Support:** 4 observations across 4 repositories
- **Directional consistency:** 100% improvements, 0 regressions
- **Measured delta summary:** no absolute delta values were supplied