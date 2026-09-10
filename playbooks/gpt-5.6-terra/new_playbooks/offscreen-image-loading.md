---
issue_type: offscreen-image-loading
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
required_validation:
- offscreen_image_candidates_confirmed
- image_dimensions_or_aspect_ratio_known
- gallery_initial_viewport_scope_known
- image_not_required_for_immediate_interaction
forbidden_techniques: []
flavor_overrides: {}
source_prs:
- esc-chula/larngearcamp-frontend#2
- alkemyTech/OT144-CLIENT#63
- widgetbot-io/message-renderer#4
- dawiddworak88/Giuru#281
---
# Offscreen image loading

> **Risk tier:** medium

## What this addresses

The evidence PRs add lazy-loading components for image attachments and galleries. One implementation also supplies a placeholder with the attachment image's known width and height.

## When to apply / when to skip
**Apply when:**
- A gallery, attachment list, or image feed contains images outside the initial viewport.
- Each deferred image has known `width` and `height`, or its container has a stable `aspect-ratio`.
- The image is not required for an immediately available interaction, such as the currently selected product-gallery slide.

**Skip when:**
- The candidate image appears above the fold or is likely to enter the viewport during initial render.
- Image dimensions cannot be reserved without causing layout shift.
- The gallery implementation requires a broad rewrite of its carousel, dialog, or image-component lifecycle.
- The image is a meaningful fallback for users without JavaScript and the implementation would remove its usable `src` without a server-rendered alternative.

## Recommended approaches

### Use a lazy-loading image component for attachments

The evidence includes an attachment image component styled from `react-lazy-load-image-component`. It passes the image URL, width, height, and a placeholder sized with the same dimensions.

```tsx
import { LazyLoadImage } from "react-lazy-load-image-component";

function ImageAttachment({ attachment, width, height }) {
  return (
    <LazyLoadImage
      src={attachment.url}
      width={width}
      height={height}
      placeholder={
        <div style={{ width, height }}>
          Loading...
        </div>
      }
    />
  );
}
```

Keep the attachment dimensions available to both the image and its placeholder.

### Wrap reusable image markup in a lazy-loading component

The evidence also includes a reusable React component based on `react-lazyload` that accepts an image source, alternative text, and an optional CSS class.

```jsx
import LazyLoad from "react-lazyload";

export default function LazyLoadImages({ src, altText, classText = "" }) {
  return (
    <LazyLoad>
      <img
        src={src}
        alt={altText}
        className={classText}
      />
    </LazyLoad>
  );
}
```

Provide an optional class or equivalent styling hook when introducing a shared image component.

### Preserve responsive image data in gallery models

The product-gallery evidence replaces separate original and thumbnail fields with an image source, alternative text, and a collection of responsive sources.

```csharp
public class ImageViewModel
{
    public string ImageSrc { get; set; }
    public string ImageAlt { get; set; }
    public IEnumerable<SourceViewModel> Sources { get; set; }
}
```

Keep image source, alternative text, and responsive source data available to the gallery UI.

## Anti-patterns

### Lazy-loading an initially visible image

```html
<!-- Avoid applying the deferred-image treatment to the initially visible image -->
<img src="/content/dam/site/hero.webp"
     alt="New collection"
     loading="lazy"
     width="1600"
     height="900">
```

**Why this is bad:** the image is not an offscreen candidate.

### Deferring images without reserving their layout space

```html
<!-- Avoid deferring an image when no dimensions or stable container ratio are available -->
<div class="gallery__item">
  <img data-src="/media_1234567890abcdef/detail.webp"
       alt="Product detail">
</div>
```

**Why this is bad:** the evidence implementation supplies known width and height to the lazy-loaded image and its placeholder.

### Adding a shared lazy-loading component without a styling hook

```jsx
// Avoid a shared component that cannot accept image styling
export default function LazyLoadImages({ src, altText }) {
  return (
    <LazyLoad>
      <img src={src} alt={altText} />
    </LazyLoad>
  );
}
```

**Why this is bad:** the evidence review specifically requests an optional class prop so callers can change image presentation.

## Implementation notes

The evidence shows two React lazy-loading libraries:

- `react-lazy-load-image-component` for an attachment image with a sized placeholder.
- `react-lazyload` for a reusable image wrapper and gallery-related work.

Use the image component or wrapper only for confirmed offscreen candidates, retain available dimensions, and preserve alternative text.