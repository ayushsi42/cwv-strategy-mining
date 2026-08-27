---
issue_type: resource-prioritization--preload-the-hero-image-before-it-is-discovered-in-markup
parent_strategy: resource-prioritization
risk_tier: low
cwv_metrics: [LCP]
source_prs:
  - Pinback-Team/pinback-client#207
  - katehallyal/react-native-renderer#11
  - woowacourse/perf-basecamp#161
  - woowacourse/perf-basecamp#178
required_validation:
  - hero_image_is_discoverable_in_markup
  - hero_image_is_the_lcp_candidate
forbidden_techniques: []
---

# Preload the hero image before it is discovered in markup

> **Risk tier:** low · **Parent strategy:** resource-prioritization · **CWV metric:** LCP

## What this addresses

This strategy reduces discovery delay for the primary hero image by making the browser aware of it earlier than the normal markup path would. The evidence supports two related mechanisms:

1. A document-level preload for the hero image.
2. A high-priority request on the actual hero `<img>` element.

The intended effect is to start the hero image request earlier so it is more likely to be available when the page reaches its LCP moment.

## When to apply / when to skip

### Apply when
- The hero image is a meaningful LCP candidate.
- The image source is known at document render time.
- The preload can point to the same resource the page will actually render.
- The hero image is not already discovered early enough by the browser.

### Skip when
- The page does not have a stable hero image candidate.
- The image source is not known when the document is generated.
- The image is not the LCP-relevant element.
- The preload target cannot be kept aligned with the rendered image source.
- The page already discovers the image early enough and there is no evidence of benefit.

## Required validation

### `hero_image_is_discoverable_in_markup`

**What this means:**  
The hero image must be referenced in markup or in a document-head preload target that the browser can resolve directly.

**Evidence-derived examples:**
- A `<link rel="preload" as="image" href="...">` entry in `index.html`.
- A hero `<img>` with a concrete `src` derived from a known asset import.
- A responsive preload using `imagesrcset` and `imagesizes` when the hero image is selected by viewport conditions.

**What to verify:**
- The preload URL matches the actual hero image resource or the responsive candidate set.
- The rendered page still uses the same image family or asset set.

### `hero_image_is_the_lcp_candidate`

**What this means:**  
The preloaded image must be the page’s primary above-the-fold visual target, not a secondary decorative asset.

**Evidence-derived examples:**
- The image is the large scene/hero visual in the main content area.
- The preload is added specifically for the page’s main visual asset.
- The change is paired with `fetchpriority="high"` or `loading="eager"` on the same hero image.

**What to verify:**
- The image is the dominant visual element in the initial viewport.
- The preload is not being used for non-critical imagery.

## Recommended approaches

Use one of the following supported shapes, depending on how the hero image is delivered.

### Good: preload a known hero image in the document head

```html
<link
  rel="preload"
  as="image"
  href="https://dcfvpdk3qtkru.cloudfront.net/static/hero.avif"
  type="image/avif"
  fetchpriority="high"
/>
```

**Why this is supported:**  
The evidence shows a document-level preload for a hero image that is known ahead of time and can be requested directly.

### Good: preload the same hero asset that the page renders

```html
<link
  rel="preload"
  as="image"
  href="/src/assets/Lv.1.webp"
  fetchpriority="high"
/>
```

```tsx
<img
  src={src}
  draggable={false}
  loading="eager"
  decoding="async"
  fetchPriority="high"
  width={1200}
  height={810}
/>
```

**Why this is supported:**  
The evidence shows a hero image imported from a known asset and the rendered `<img>` marked eager/high priority.

### Good: preload a responsive hero image candidate set

```html
<link
  rel="preload"
  as="image"
  imagesrcset="/static/hero-480.webp 480w, /static/hero-1200.webp 1200w, /static/hero.webp 1920w"
  imagesizes="(max-width: 600px) 480px, (max-width: 1200px) 1200px, 1920px"
/>
```

**Why this is supported:**  
The evidence shows a responsive preload that mirrors the hero image candidate selection logic.

## Anti-patterns

The supplied evidence does not include a defensible pre-change regression patch showing a specific bad implementation for this strategy. Because of that, no concrete forbidden technique is justified here.

## How to verify

Use before/after measurement on the same page and under the same test conditions.

### Supported signals from the evidence
- LCP
- Lighthouse LCP / preload key requests
- Human review focused on LCP and preload fallback

### Verification steps
1. Record the baseline LCP and Lighthouse output for the page.
2. Apply the preload and, where supported, the high-priority hero image attributes.
3. Re-run the same measurement.
4. Confirm that the hero image is requested earlier and that the LCP result is not worse.

### Measurable acceptance criteria
- The hero image request appears earlier in the network waterfall after the change.
- The hero image remains the same resource or responsive candidate set before and after the change.
- LCP does not regress under the same test setup.

Do not assume a fixed improvement. The evidence supports directional validation only.

## Evidence and confidence

### Observed facts
- `Pinback-Team/pinback-client#207` added a document preload for `/src/assets/Lv.1.webp` and marked the hero `<img>` with `loading="eager"`, `decoding="async"`, `fetchPriority="high"`, and explicit dimensions.
- `woowacourse/perf-basecamp#161` added a document preload for a hero image served from CloudFront with `as="image"`, `type="image/avif"`, and `fetchpriority="high"`.
- `woowacourse/perf-basecamp#178` added a responsive image preload using `imagesrcset` and `imagesizes` for the hero image set.

### Inference
- These patches support the same mechanism: make the hero image discoverable earlier so the browser can prioritize it for LCP.
- The evidence supports this as a low-risk resource-prioritization tactic when the image target is stable and known ahead of time.

### Confidence
- Confidence is medium, based on 3 repositories and 4 improvement observations with consistent directionality.

## Risks and limitations

- A preload only helps if it points to the same resource the page actually uses.
- Responsive hero images need the preload candidate set to stay aligned with the rendered selection logic.
- Overusing preload for non-critical images can waste bandwidth and compete with more important resources.
- The evidence does not establish universal browser behavior guarantees or a fixed performance gain.

## Evidence separation

### Evidence
- Document-level hero image preloads were added in the supplied patches.
- Hero images were marked with high-priority loading attributes in at least one patch.
- A responsive preload variant was also used for a hero image set.

### Inference
- Earlier discovery can reduce request delay for the hero image.
- Earlier request start can improve the chance that the image is ready for LCP.

### Not established by the evidence
- A universal performance gain for every page.
- A specific numeric LCP improvement.
- A specific anti-pattern regex or forbidden code pattern.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (4 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **4 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: resource-prioritization--preload-the-hero-image-before-it-is-discovered-in-markup`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
