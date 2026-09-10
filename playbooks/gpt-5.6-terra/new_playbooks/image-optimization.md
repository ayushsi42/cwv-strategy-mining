---
issue_type: image-optimization
applicable_flavors:
- cs
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- allaboutmike/2023-Cohort-Projects#61
- keploy/blog-website#19
- Nileshdcool/medmonk#3
- e-Learning-by-SSE/nm-self-learning#165
- alchemyplatform/aa-sdk#1376
---
## Image optimization

> **CWV metric:** LCP

## What this addresses

Using native `<img>` elements can result in slower LCP and higher bandwidth. In Next.js applications, consider using `<Image />` from `next/image` to automatically optimize images. This may incur additional usage or cost from the image provider.

## When to apply / when to skip
**Apply when:**
- A Next.js lint warning reports `@next/next/no-img-element`.
- An image is a material LCP contributor.

## Recommended approaches

### Use Next.js Image for content images

```tsx
import Image from "next/image";

<Image
  src={heroImage}
  alt={heroTitle}
  width={1200}
  height={800}
/>
```

## Anti-patterns

### Using a native image element where Next.js image optimization is appropriate

```tsx
// This can result in slower LCP and higher bandwidth.
<img
  src={heroAssetPath}
  className="hero-image"
  alt={heroTitle}
/>
```

## Flavor-specific notes

### Next.js

Use `<Image />` from `next/image` where appropriate to use Next.js image optimization.