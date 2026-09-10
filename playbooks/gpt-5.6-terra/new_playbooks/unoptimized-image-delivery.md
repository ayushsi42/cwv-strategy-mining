---
issue_type: unoptimized-image-delivery
applicable_flavors:
- cs
risk_tier: high
required_validation: []
forbidden_techniques: []
source_prs:
- serlo/frontend#2115
- modern-agile-team/dongurami-front-v2#64
- CodeForPhilly/vacant-lots-proj#417
- ChaSaji/PickNic#162
- Sprint-Part3-14Team/14team-project#41
- ABC-TransitionBasCarbone/bilan-carbone#249
- VTKLeuven/burgieclan#159
- BuidlGuidl/batch16.buidlguidl.com#21
- TinU-Official/TinU-Client#105
---
# Unoptimized image delivery

> **CWV metric:** LCP

## What this addresses

Unoptimized images can contribute to higher bandwidth use and slower LCP. Use an image component or loader that automatically optimizes images, and provide image dimensions when the implementation requires them.

## When to apply / when to skip
**Apply when:**
- Lighthouse identifies unoptimized images as a contributor to the page’s performance score.
- The page uses plain `<img>` elements and the framework reports that they could result in slower LCP or higher bandwidth.
- Large images are loaded before they are needed.

**Skip when:**
- The audited page has no relevant image delivery issue.
- Replacing the current image implementation cannot be done safely.

## Recommended approaches

### Use the framework image component or a custom image loader

Where available, use the framework’s optimized image component instead of a plain `<img>` element.

```tsx
import Image from "next/image";

<Image
  src={imageSource}
  alt="Product hero"
  width={1200}
  height={800}
/>
```

The evidence PRs use `next/image` in response to warnings that plain `<img>` elements could result in slower LCP and higher bandwidth. The component can support image resizing and lazy loading; provide dimensions when they are required by the implementation.

### Configure approved remote image sources

When optimized images are served from remote hosts, configure the allowed remote source patterns or domains.

```js
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "assets.example.com",
        pathname: "/**",
      },
    ],
  },
};
```

### Let non-critical images load lazily

For pages with many images, defer images until they are needed rather than loading all of them during initial page load. The evidence PRs identify missing lazy loading and large images as a performance concern.

## Anti-patterns

### Rendering images with a plain `<img>` element without optimization

```html
<!-- Bad: plain image delivery without an optimization component or loader -->
<img src="/images/product-hero.jpg" alt="Product hero">
```

**Why this is bad:** Framework warnings in the evidence state that using `<img>` can result in slower LCP and higher bandwidth. Use an optimized image component or custom image loader where appropriate.