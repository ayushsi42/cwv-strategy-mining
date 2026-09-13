---
issue_type: image-discovery-delay
applicable_flavors:
- cs
- ams
risk_tier: medium
required_validation: []
forbidden_techniques: []
source_prs:
- alveusgg/alveusgg#142
- woowacourse/frontend-rendering#40
- mobi-projects/nail-case-client#73
- eCOO-FURG/apps#167
- rak517/Epigram#163
---
# Image discovery delay

> **Risk tier:** medium · **CWV metric:** LCP

## What this addresses

LCP measures when the largest image or text in the viewport is rendered. For a verified image LCP element, delayed image loading can delay LCP.

The evidence shows Next.js `Image` components being given `priority` for images treated as LCP candidates, including a signup-page logo and the first image in a slideshow. The cited implementation notes state that `priority` removes lazy loading and adds an image preload.

## When to apply / when to skip
**Apply when:**
- Measurement identifies an image in the initial viewport as the LCP element.
- The image is the specific image to prioritize, such as the first visible slideshow image.
- The page uses a Next.js `Image` component.

**Skip when:**
- The LCP element is not an image.
- The candidate image is not the measured LCP element.
- The image is not the initially visible image in a slideshow or similar component.
- The image already has the required priority treatment.

Validate the change with measurement after deployment. Confirm that the image receiving priority is the image identified as the LCP candidate.

## Recommended approaches

### Give the verified LCP image Next.js priority

Add `priority` only to the `Image` instance used for the verified LCP image.

```html
<link
  rel="preload"
  as="image"
  href="/content/dam/site/hero/new-product-collection.jpg"
/>

<img
  src="/content/dam/site/hero/new-product-collection.jpg"
  alt="New product collection"
  width="1920"
  height="900"
  loading="eager"
  fetchpriority="high"
/>
```

The cited Next.js implementation notes state that `priority` disables lazy loading and emits a preload link for the image.

### Prioritize only the initially visible slideshow image

For a slideshow, apply priority conditionally to the initially displayed image.

```html
<div class="slideshow">
  <img
    src="/content/dam/site/slides/slide-1.jpg"
    alt="New product collection"
    width="1920"
    height="900"
    loading="eager"
    fetchpriority="high"
  />
  <img
    src="/content/dam/site/slides/slide-2.jpg"
    alt="Seasonal offers"
    width="1920"
    height="900"
    loading="lazy"
  />
  <img
    src="/content/dam/site/slides/slide-3.jpg"
    alt="Featured products"
    width="1920"
    height="900"
    loading="lazy"
  />
</div>
```

This follows the cited homepage change, which assigned priority to the first slideshow image.

### Keep priority local to the LCP context

Place `priority` on the page, hero, or slideshow instance that renders the measured LCP image rather than adding it unconditionally to every use of a shared image component.

```html
<section class="hero">
  <img
    src="/content/dam/site/hero/new-product-collection.jpg"
    alt="New product collection"
    width="1920"
    height="900"
    loading="eager"
    fetchpriority="high"
  />
</section>
```

## Anti-patterns

### Adding priority to every image without identifying the LCP image

```html
<!-- Bad: every image receives high fetch priority -->
<img
  src="/content/dam/site/logo.svg"
  alt="Site logo"
  width="172"
  height="48"
  loading="eager"
  fetchpriority="high"
/>
<img
  src="/content/dam/site/cards/card-one.jpg"
  alt="Card one"
  width="640"
  height="360"
  loading="eager"
  fetchpriority="high"
/>
<img
  src="/content/dam/site/cards/card-two.jpg"
  alt="Card two"
  width="640"
  height="360"
  loading="eager"
  fetchpriority="high"
/>
```

**Why this is bad:** The evidence supports applying priority to an identified LCP candidate, such as a signup logo treated as LCP or the first slideshow image. It does not support applying priority to every image.

### Leaving the verified LCP image without priority

```html
<!-- Bad when this image is the measured LCP candidate -->
<img
  src="/content/dam/site/hero/new-product-collection.jpg"
  alt="New product collection"
  width="1920"
  height="900"
  loading="lazy"
/>
```

**Why this is bad:** The cited implementation notes identify missing priority on a viewport LCP image as a possible cause of delayed LCP and state that Next.js `priority` removes lazy loading and adds preload treatment.

### Prioritizing a non-initial slideshow image

```html
<!-- Bad: a later slide is prioritized instead of the initial slide -->
<div class="slideshow">
  <img
    src="/content/dam/site/slides/slide-1.jpg"
    alt="New product collection"
    width="1920"
    height="900"
    loading="lazy"
  />
  <img
    src="/content/dam/site/slides/slide-2.jpg"
    alt="Seasonal offers"
    width="1920"
    height="900"
    loading="lazy"
  />
  <img
    src="/content/dam/site/slides/slide-3.jpg"
    alt="Featured products"
    width="1920"
    height="900"
    loading="eager"
    fetchpriority="high"
  />
</div>
```

**Why this is bad:** The cited slideshow implementation prioritizes the first image (`idx === 0`), not every slide or a later slide.