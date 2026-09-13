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
- The page uses plain `<img>` elements and the implementation serves original or oversized image assets that could result in slower LCP or higher bandwidth.
- Large images are loaded before they are needed.

**Skip when:**
- The audited page has no relevant image delivery issue.
- Replacing the current image implementation cannot be done safely.

## Recommended approaches

### Use the Core Image Component or an AEM image delivery configuration

Where available, use the AEM Core Image Component instead of rendering a plain `<img>` element directly.

```html
<sly data-sly-resource="${'product-hero' @
  resourceType='core/wcm/components/image/v3/image',
  decorationTagName='div',
  cssClassName='product-hero'}" />
```

The Core Image Component can use configured DAM renditions and responsive image delivery rather than serving an original asset directly. Configure rendition widths and lazy-loading behavior in the component policy, and provide width and height information when required by the component implementation.

### Configure approved remote image sources

When optimized images are served from remote hosts, configure the allowed remote source patterns or domains.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="nt:unstructured"
          sling:resourceType="wcm/core/components/policy/policy"
          allowedRenditionWidths="[400,800,1200]"/>
```

### Let non-critical images load lazily

For pages with many images, defer images until they are needed rather than loading all of them during initial page load. The evidence PRs identify missing lazy loading and large images as a performance concern.

## Anti-patterns

### Rendering images with a plain `<img>` element without optimization

```html
<!-- Bad: HTL renders the original DAM asset directly without the Core Image component. -->
<img data-sly-attribute.src="${properties.fileReference @ context='uri'}"
     alt="${properties.alt}">
```

**Why this is bad:** Serving original DAM assets directly can result in slower LCP and higher bandwidth. Use the Core Image Component or a custom AEM image-delivery implementation where appropriate.