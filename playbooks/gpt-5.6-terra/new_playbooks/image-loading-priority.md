---
issue_type: image-loading-priority
applicable_flavors:
- cs
- ams
risk_tier: medium
required_validation:
- lcp_via_lighthouse_attribution
- image_visible_in_initial_viewport
- template_and_component_scope_known
- responsive_viewport_priority_candidates_traced
- no_competing_high_priority_images
- image_rendered_in_initial_html
forbidden_techniques:
- pattern: <img(?=[^>]*\bdata-sly-list\b)(?=[^>]*\bfetchpriority\s*=\s*["']high["'])[^>]*>
  reason: Don't assign fetchpriority="high" to every image emitted by a list; multiple
    prioritized list images can compete with the actual LCP image.
- pattern: <img(?=[^>]*\bdata-sly-list\b)(?=[^>]*\bloading\s*=\s*["']eager["'])[^>]*>
  reason: Don't eagerly load every image in a repeated list; retain lazy loading for
    cards and images outside the confirmed initial viewport.
flavor_overrides:
  cs:
    extra_validation:
    - image_component_htl_output_verified
    - adaptive_image_servlet_url_preserved
  ams:
    extra_validation:
    - verify_jsp_or_htl_output_path
    - legacy_image_servlet_behavior_verified
source_prs:
- sprint-19-part4-1team/global-nomad#292
- simonyiszk/mszk#21
- vercel/commerce#1143
- woowacourse/frontend-rendering#40
- J-P-plan/J-P_FE#9
---
# Image loading priority

> **Risk tier:** medium · **Applies to:** CS, AMS · **CWV metric:** LCP

## What this addresses

Images marked eager or `fetchpriority="high"` can compete with other image requests. Restrict elevated priority to images confirmed to be visible in the initial viewport and identified as LCP candidates, rather than applying it to card, gallery, or list images by default.

## When to apply / when to skip
**Apply when:**
- Lighthouse element attribution identifies an image as the LCP element on the affected page and viewport.
- The template, component, and rendered `<img>` output path are known.
- The candidate image is present in the initial HTML and visible without scrolling.
- Multiple eager or high-priority image requests are present during the LCP request window.
- The priority candidate has been checked at the responsive viewport used for the audit.

**Skip when:**
- The LCP element is text, video, a CSS background, or a consent overlay rather than an `<img>`.
- The candidate image is inserted only after client-side JavaScript runs.
- Different responsive breakpoints produce different above-the-fold images and no per-viewport rule can be safely scoped.
- The shared image component is used across unrelated templates and there is no reliable hero or lead-image context.
- The existing high-priority image is already the confirmed LCP image and there are no competing image requests to remove.

## Recommended approaches

### Scope high priority to a confirmed hero context

Expose an explicit component context rather than making every image emitted by a shared image component eager. Only return elevated-priority values for the template placement that Lighthouse confirms is the LCP image.

```java
// Good — core/src/main/java/com/example/site/core/models/HeroImageModel.java
package com.example.site.core.models;

import org.apache.sling.api.SlingHttpServletRequest;
import org.apache.sling.models.annotations.Model;
import org.apache.sling.models.annotations.injectorspecific.ValueMapValue;

@Model(
    adaptables = SlingHttpServletRequest.class,
    resourceType = "example/components/content/hero-image"
)
public class HeroImageModel {

    @ValueMapValue
    private boolean lcpCandidate;

    public String getLoading() {
        return lcpCandidate ? "eager" : "lazy";
    }

    public String getFetchPriority() {
        return lcpCandidate ? "high" : "auto";
    }
}
```

```html
<!-- Good — ui.apps/.../hero-image/hero-image.html -->
<sly data-sly-use.hero="com.example.site.core.models.HeroImageModel" />

<img src="${properties.fileReference @ context='uri'}"
     alt="${properties.alt}"
     width="${properties.width}"
     height="${properties.height}"
     loading="${hero.loading}"
     fetchpriority="${hero.fetchPriority}">
```

The explicit `lcpCandidate` authoring or template policy flag can confine high priority to the hero placement. Keep `width` and `height` to reserve layout space; see [`image-sizing.md`](./image-sizing.md).

### Keep repeated cards and gallery images lazy

List and gallery images should not receive elevated priority by default. Leave them at normal browser priority unless a real-page trace shows that a specific visible lead image is the LCP candidate.

```html
<!-- Good — ui.apps/.../experience-gallery/experience-gallery.html -->
<sly data-sly-list.image="${gallery.images}">
  <article class="experience-gallery__card">
    <img src="${image.renditionUrl @ context='uri'}"
         alt="${image.alt}"
         width="${image.width}"
         height="${image.height}"
         loading="lazy"
         fetchpriority="auto">
  </article>
</sly>
```

This avoids assigning elevated priority to every image in the list. Verify whether images in the initial viewport need a separately scoped rule.

### Prioritize only the lead image in a responsive image grid

A grid may have a single visually dominant image on a given template. Scope elevated priority to that lead image only after verifying that it remains above the fold and is the LCP candidate at the audited viewport.

```html
<!-- Good — ui.apps/.../activity-image-grid/activity-image-grid.html -->
<sly data-sly-list.image="${grid.images}">
  <div class="activity-image-grid__item">
    <sly data-sly-test.isLead="${imageList.first}">
      <img src="${image.renditionUrl @ context='uri'}"
           alt="${image.alt}"
           width="${image.width}"
           height="${image.height}"
           loading="eager"
           fetchpriority="high">
    </sly>
    <sly data-sly-test="${!isLead}">
      <img src="${image.renditionUrl @ context='uri'}"
           alt="${image.alt}"
           width="${image.width}"
           height="${image.height}"
           loading="lazy"
           fetchpriority="auto">
    </sly>
  </div>
</sly>
```

Use this only where the first grid item is consistently the dominant, attributed LCP image. If mobile changes the grid order or makes another image dominant, use separate template or component variants instead of globally prioritizing all grid items.

## Anti-patterns

### Marking every repeated card image as high priority

```html
<!-- Bad: every list item bypasses lazy loading and receives elevated priority -->
<sly data-sly-list.image="${gallery.images}">
  <img src="${image.renditionUrl @ context='uri'}"
       alt="${image.alt}"
       width="${image.width}"
       height="${image.height}"
       loading="eager"
       fetchpriority="high">
</sly>
```

**Why this is bad:** Applying priority to every repeated image can prevent lazy loading for all list items and can create competing image requests. Reviewers in the evidence specifically flagged priority on each list item as a possible performance regression.

### Making high priority the default of a shared image component

```java
// Bad — every component using this model receives high priority
public String getFetchPriority() {
    return "high";
}
```

```html
<!-- Bad: shared image component always emits elevated priority -->
<img src="${properties.fileReference @ context='uri'}"
     alt="${properties.alt}"
     loading="eager"
     fetchpriority="high">
```

**Why this is bad:** A shared component may be used for images that are not visible in the initial viewport. A default eager or high-priority setting can therefore prioritize non-LCP images.

### Preloading gallery or carousel images

```html
<!-- Bad: preloads a gallery rendition without confirming it is the LCP image -->
<link rel="preload"
      as="image"
      href="/content/dam/example/gallery/card-03.jpg"
      imagesrcset="/content/dam/example/gallery/card-03.jpg 640w,
                   /content/dam/example/gallery/card-03-large.jpg 1280w">
```

**Why this is bad:** Do not preload a gallery image unless it is confirmed as the relevant LCP image for the audited viewport. Preloading additional non-LCP images can add competing early image requests.

## Flavor-specific notes

### CS

Prefer a template-scoped hero or lead-image policy over changing a global image component when the component is shared. Verify the rendered image output and preserve the existing responsive rendition URL when adding `loading` or `fetchpriority` attributes.

When a component is shared between landing pages and content pages, scope any LCP flag to the verified hero placement rather than setting it as a shared default.

### AMS

Confirm whether the rendered `<img>` originates from HTL, a JSP include chain, or an image servlet before editing. Preserve the existing generated image URL and add priority attributes only at the verified output point.

If the component is JSP-driven and the include chain is not statically traceable, use a manually reviewed change scoped to the specific hero template.