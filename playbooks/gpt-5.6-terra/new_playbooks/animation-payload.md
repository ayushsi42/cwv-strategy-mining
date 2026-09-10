---
issue_type: animation-payload
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: high
required_validation:
- lottie_runtime_and_json_attributed_to_lcp_or_inp
- animation_is_not_required_for_primary_content_or_task_completion
- animation_visual_behavior_reviewed_by_design_owner
- static_or_reduced_motion_fallback_available
- viewport_or_interaction_activation_boundary_defined
forbidden_techniques:
- pattern: \bimport\s+(?:[\w*$\s{},]+)\s+from\s+['"](?:lottie-web|@lottiefiles/dotlottie-web)['"]
  reason: Do not add a static Lottie runtime import to an initial-page entry without
    reviewing its loading and activation behavior.
- pattern: \bnew\s+DotLottie\s*\(\s*\{
  reason: Do not add unconditional DotLottie initialization without reviewing whether
    animation creation should wait for a viewport or user-interaction trigger.
flavor_overrides:
  eds:
    extra_validation:
    - block_is_not_lcp_content_or_above_fold_critical
  cs:
    extra_validation:
    - clientlib_category_scope_and_template_inclusions_traced
  ams:
    extra_validation:
    - clientlib_category_scope_and_jsp_or_htl_output_path_traced
  headless:
    extra_validation:
    - client_rendering_owner_and_hydration_boundary_identified
source_prs:
- okp4/dataverse-portal#491
- web-infra-dev/rspack#7702
- cybersemics/em#2462
- canonical/canonical.com#1725
---
# Animation payload

> **Risk tier:** high · **Applies to:** EDS, CS, AMS, headless · **CWV metric:** LCP, INP

## What this addresses

The evidence PRs add Lottie runtimes and animation JSON assets. One PR statically imports both `@lottiefiles/dotlottie-web` and `lottie-web` and creates autoplaying hero animations during module evaluation. Another adds `lottie-web` and JSON animation files to a landing-page codebase.

A reviewer on the Canonical homepage PR reported that Lighthouse performance had fallen to 68 after the homepage revamp. The supplied evidence does not establish which change caused that score change or attribute it specifically to Lottie, LCP, or INP.

This is recommendation-only: changing animation timing, motion, or fallbacks can alter a design's intended behavior and requires design and accessibility review before implementation.

## When to apply / when to skip
**Apply when:**
- A performance trace attributes JavaScript download, animation-asset processing, rendering work, or long tasks to a Lottie runtime or animation asset.
- The animation is decorative, below the fold, or starts only after a user interaction.
- A static image, SVG, or reduced-motion representation is available and has been reviewed by the design owner.
- The site can identify a safe viewport or interaction boundary for animation activation.

**Do not apply when:**
- The animation is the LCP element, communicates primary page content, or is required to complete a task.
- There is no approved static, reduced-motion, or failure fallback.
- The animation's visual timing is contractually required, such as for product demonstrations or regulated instructions.
- The rendering path, clientlib inclusion, block ownership, or headless hydration owner cannot be traced.

## Recommended approaches

### Use a static visual for decorative or non-essential motion

Prefer an optimized SVG or image when motion does not communicate information. A static implementation does not require a Lottie runtime or Lottie animation JSON for that visual.

```html
<!-- Example: approved static fallback for a decorative animation -->
<div class="feature-illustration">
  <img src="/content/dam/site/illustrations/security-check.svg"
       alt=""
       width="128"
       height="128">
</div>
```

Confirm that empty `alt` text is correct for decorative content.

### Defer a below-the-fold EDS block until it enters the viewport

For an approved EDS animation block that is not above the fold, retain a static fallback in the initial markup and load the animation controller only after the block approaches the viewport.

```javascript
// Example: blocks/feature-animation/feature-animation.js
export default function decorate(block) {
  const poster = block.querySelector('img');
  const animationSrc = block.dataset.animationSrc;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (!animationSrc || reducedMotion.matches || typeof IntersectionObserver === 'undefined') {
    return;
  }

  const observer = new IntersectionObserver(async ([entry]) => {
    if (!entry.isIntersecting) return;

    observer.disconnect();

    const { startAnimation } = await import('./lottie-player.js');
    await startAnimation(block, animationSrc, poster);
  }, { rootMargin: '300px 0px' });

  observer.observe(block);
}
```

```html
<!-- Example: initial EDS block content remains meaningful without JavaScript -->
<div class="feature-animation"
     data-animation-src="/media_abc123/lottie/security-check.json">
  <img src="/media_abc123/illustrations/security-check.svg"
       alt=""
       width="128"
       height="128">
</div>
```

In this example, the dynamic import is reached only after an intersecting entry is observed. The image remains in the initial markup.

### Scope an approved CS or AMS animation component and render its fallback first

For CS or AMS, render a fallback from a Sling Model and scope optional component behavior to a dedicated clientlib category rather than a global page clientlib. Trace every template or component inclusion before changing clientlib scope.

```xml
<!-- Example: ui.apps/.../clientlibs/clientlib-feature-animation/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.feature-animation]"
          dependencies="[site.base]"/>
```

```text
# Example: ui.apps/.../clientlibs/clientlib-feature-animation/js.txt
#base=js
feature-animation.js
```

```html
<!-- Example: component.html -->
<sly data-sly-use.animation="com.site.core.models.FeatureAnimationModel" />

<div class="cmp-feature-animation"
     data-animation-src="${animation.animationJson @ context='uri'}">
  <img src="${animation.fallbackImage @ context='uri'}"
       alt="${animation.alt}"
       width="${animation.width}"
       height="${animation.height}">
  <button data-sly-test="${animation.userActivated}"
          class="cmp-feature-animation__play"
          type="button">
    Play animation
  </button>
</div>
```

```java
// Example: FeatureAnimationModel.java
package com.site.core.models;

import com.adobe.cq.sightly.WCMUsePojo;
import org.apache.sling.api.SlingHttpServletRequest;
import org.apache.sling.models.annotations.Model;
import org.apache.sling.models.annotations.injectorspecific.ValueMapValue;

@Model(adaptables = SlingHttpServletRequest.class)
public class FeatureAnimationModel {
  @ValueMapValue private String animationJson;
  @ValueMapValue private String fallbackImage;
  @ValueMapValue private String alt;
  @ValueMapValue private boolean decorative;
  @ValueMapValue private boolean userActivated;
  @ValueMapValue private String width;
  @ValueMapValue private String height;

  public String getAnimationJson() { return animationJson; }
  public String getFallbackImage() { return fallbackImage; }
  public String getAlt() { return decorative ? "" : alt; }
  public boolean isUserActivated() { return userActivated; }
  public String getWidth() { return width; }
  public String getHeight() { return height; }
}
```

The example renders an image before optional JavaScript runs. A human reviewer must decide whether viewport activation or explicit user activation is appropriate.

### Respect reduced motion before loading an optional animation

For non-essential motion, check the user’s reduced-motion preference before registering an activation path that imports the animation controller.

```javascript
// Example: blocks/feature-animation/feature-animation.js
export default function decorate(block) {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const playButton = block.querySelector('.cmp-feature-animation__play');

  if (reducedMotion.matches || !playButton) return;

  playButton.addEventListener('click', async () => {
    const animationSrc = block.dataset.animationSrc;
    if (!animationSrc) return;

    const { startAnimation } = await import('./lottie-player.js');
    await startAnimation(block, animationSrc);
  }, { once: true });
}
```

In this example, the dynamic import is reached only after a click by a user who does not request reduced motion.

## Anti-patterns

### Statically importing and autoplaying hero Lottie animations

```xml
<!-- ui.apps/.../clientlibs/clientlib-homepage-animations/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.homepage-animations]"
          dependencies="[site.base]"/>
```

```text
# ui.apps/.../clientlibs/clientlib-homepage-animations/js.txt
#base=js
vendor/lottie.min.js
homepage-animations.js
```

```javascript
// ui.apps/.../clientlibs/clientlib-homepage-animations/js/homepage-animations.js
(function () {
  const lightCanvas = document.querySelector('.hero-section-suru-light');
  const shadowCanvas = document.querySelector('.hero-section-suru-shadow');

  if (!window.lottie || !lightCanvas || !shadowCanvas) return;

  window.lottie.loadAnimation({
    container: lightCanvas,
    renderer: 'canvas',
    loop: false,
    autoplay: true,
    path: '/content/dam/site/animations/suru_light.json',
  });

  window.lottie.loadAnimation({
    container: shadowCanvas,
    renderer: 'canvas',
    loop: false,
    autoplay: true,
    path: '/content/dam/site/animations/suru_shadow.json',
  });
}());
```

**Why this needs review:** The Canonical PR statically imports both runtimes and constructs two autoplaying `DotLottie` instances in the module. Its build configuration adds this module as a `homepage_animations` entry. The supplied evidence does not show a viewport, interaction, or reduced-motion boundary around these initializations.

### Bundling Lottie JSON with a component that renders on initial load

```javascript
// ui.apps/.../clientlibs/clientlib-feature-animation/js/feature-animation.js
(function () {
  const animation = document.querySelector('.cmp-feature-animation');
  if (!animation || !window.lottie) return;

  window.lottie.loadAnimation({
    container: animation,
    renderer: 'svg',
    loop: true,
    autoplay: true,
    path: animation.dataset.animationSrc,
  });
}());
```

**Why this needs review:** The Rspack PR adds `lottie-web` and JSON animation assets, but the supplied evidence does not show the component code that imports or initializes those assets. If an animation JSON import and autoplay initialization are added to an initial-render path, review whether the animation is needed before a viewport or interaction boundary.

### Replacing a lightweight static icon with an animated runtime asset

```html
<!-- Example requiring review: component.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='site.base'}" />

<div class="feature-icon">
  <canvas class="feature-icon__lottie"></canvas>
</div>
```

**Why this needs review:** The supplied evidence does not show an AEM clientlib implementation or establish that a runtime is globally loaded. Before placing a Lottie runtime in a broadly shared clientlib, trace which pages include that clientlib and whether the animated icon is present on those pages.

## Flavor-specific notes

### EDS

Treat each animation as block-owned behavior. Keep the poster or static SVG in the block's authored HTML, and use `decorate(block)` with `IntersectionObserver` only after review confirms that the block is not LCP-critical. Do not place a Lottie runtime in `head.html` or a globally loaded EDS script.

### CS / AMS

Trace the component's rendered output and every template that includes its clientlib category before proposing a change. Avoid adding a runtime to a global `site.base` or head clientlib solely because one component uses it. Scope it to the component and ensure the fallback is rendered by HTL or JSP before optional JavaScript runs.

### Headless

Identify which client application owns hydration and animation lifecycle before making a recommendation. Preserve a server-deliverable or API-provided static fallback, and ensure any approved animation controller is activated only after that application's viewport or interaction boundary rather than during initial hydration.