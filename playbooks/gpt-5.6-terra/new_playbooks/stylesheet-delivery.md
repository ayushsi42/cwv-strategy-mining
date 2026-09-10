---
issue_type: stylesheet-delivery
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
required_validation: []
forbidden_techniques: []
flavor_overrides:
  eds:
    extra_validation: []
  cs:
    extra_validation: []
  headless:
    extra_validation: []
source_prs:
- GoogleChromeLabs/llaminator#37
- martincostello/costellobot#471
- martincostello/dependabot-helper#513
- ipfs-shipyard/helia-service-worker-gateway#112
---
# Stylesheet delivery

> **Risk tier:** validate locally · **Applies to:** validate for the implementation · **CWV metric:** validate FCP and LCP

## What this addresses

The evidence shows projects configuring CSS minification and extracting CSS into generated CSS assets. It also shows that `style-loader` injects CSS at runtime, while `css-loader` loads CSS as a string.

One source project reported that runtime style injection added approximately 3 KiB of uncompressed bundle overhead. Another source project fixed CSS being omitted from final assets by marking `*.css` as side effects and configuring CSS extraction.

## When to apply / when to skip
**Apply when:**
- Audit evidence identifies CSS injected at runtime by JavaScript, or CSS that is not minified in the production build.
- The stylesheet contains global or above-the-fold styles needed for the initial page render.
- The stylesheet order and dependencies are known, and rendered-page validation can confirm no visual regressions.
- Production CSS minification is enabled or can be enabled through the existing build and delivery configuration.

**Do not apply when:**
- The candidate CSS is needed only after a user interaction or for a below-the-fold block, where loading it with that feature is appropriate.
- Extracting the CSS would change an unknown cascade order, override author styles, or alter a shared stylesheet without template-level scope.
- The delivery layer is externally managed and the project does not own the document shell or stylesheet configuration.
- The issue is caused by a third-party stylesheet whose loading policy cannot be changed in the repository.

## Recommended approaches

### EDS: keep above-the-fold styles in the initial global stylesheet

For an EDS implementation, consider placing site-wide and above-the-fold block styles in the initial global stylesheet rather than adding them through runtime JavaScript.

```javascript
// blocks/hero/hero.js
// The hero's first-paint styles are in styles/styles.css;
// this code only defers an optional interactive enhancement.
export default function decorate(block) {
  const video = block.querySelector('video[data-autoplay-when-visible]');

  if (!video) return;

  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      video.play().catch(() => {});
      observer.disconnect();
    }
  });

  observer.observe(block);
}
```

```css
/* styles/styles.css */
/* Styles required for the initial hero paint are delivered as CSS. */
.hero {
  min-height: 32rem;
  display: grid;
  align-content: end;
}

.hero picture,
.hero img {
  display: block;
  width: 100%;
  height: auto;
}
```

Validate the built output to confirm that the stylesheet is emitted, included, and ordered as intended. Reserve runtime loading for optional behavior and non-critical block styles where appropriate.

### CS: include a scoped stylesheet category in the page head

For a CS implementation, use the project's established template-level stylesheet inclusion mechanism for first-paint styles. Scope the stylesheet to the templates that require it and validate the generated publish output.

```xml
<!-- ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/clientlib-landing-critical/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[acme.landing.critical]"
          dependencies="[acme.site.base]"
          allowProxy="{Boolean}true"/>
```

```text
# ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/clientlib-landing-critical/css.txt
landing-hero.css
landing-navigation.css
```

```html
<!-- apps/acme/components/page/landing-page/landing-page.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.css @ categories='acme.landing.critical'}"/>
```

```css
/* clientlib-landing-critical/landing-hero.css */
/* First-paint landing-page styles. */
.landing-hero {
  min-height: 32rem;
  display: grid;
  align-content: end;
}
```

Validate that the category is emitted as the expected stylesheet output and that its ordering preserves the existing cascade.

### Headless: expose initial shell styles as a stylesheet

When the headless frontend owns the HTML document shell, consider referencing the production CSS asset in the initial document instead of constructing style tags after application startup.

```html
<!-- Frontend document shell -->
<head>
  <link rel="stylesheet" href="/assets/site.min.css">
</head>
<body>
  <main id="app" data-aem-content-path="/content/acme/us/en/home"></main>
</body>
```

```css
/* /assets/site.min.css */
/* Initial layout styles needed before AEM content is hydrated. */
[data-aem-content-path] {
  display: block;
  min-height: 100vh;
}
```

Preserve the existing cascade order when moving styles out of runtime code, and inspect the production build to confirm that CSS is emitted as an asset.

## Anti-patterns

### Injecting critical CSS from JavaScript

```javascript
// Styles are added at runtime.
const style = document.createElement('style');
style.textContent = `
  .landing-hero {
    min-height: 32rem;
    display: grid;
    align-content: end;
  }
`;
document.head.append(style);
```

**Why this is bad:** The evidence shows that style-loader-based CSS injection occurs at runtime. One investigated project reported approximately 3 KiB of uncompressed bundle overhead from injection. Validate whether extraction is appropriate for the application.

### Moving all deferred block CSS into the initial stylesheet

```css
/* Consider whether every optional feature needs initial-page CSS. */
.carousel,
.accordion,
.product-configurator,
.store-locator,
.pdf-viewer,
.search-overlay {
  display: block;
}
```

**Why this is bad:** The provided evidence does not establish the performance effect of moving all deferred feature CSS into an initial stylesheet. Evaluate stylesheet scope and validate the rendered page and production output.

### Omitting CSS from webpack side-effect configuration

```json
{
  "sideEffects": false
}
```

**Why this is bad:** The evidence shows a webpack project where CSS was omitted from final assets because the package declared no side effects. That project corrected the configuration by marking CSS files as side effects.

```json
{
  "sideEffects": [
    "*.css"
  ]
}
```

## Flavor-specific notes

### EDS

Validate how the EDS implementation loads global and block styles before moving CSS. Confirm that the rendered page preserves the intended cascade order.

### CS

Use the project's established stylesheet and template-inclusion conventions. Validate the publish output, stylesheet ordering, and configured minification behavior.

### Headless

Apply this playbook only when the frontend document shell is in the repository and can be changed. Confirm that the production build emits the expected CSS asset and that the document references it as intended.