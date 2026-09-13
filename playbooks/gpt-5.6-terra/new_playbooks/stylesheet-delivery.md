---
issue_type: stylesheet-delivery
applicable_flavors:
- cs
- headless
risk_tier: medium
required_validation:
- stylesheet_render_path_traced
- css_bundle_inventory_built
- stylesheet_order_preserved
- critical_styles_available_before_first_render
- css_side_effects_preserved
forbidden_techniques: []
flavor_overrides:
  cs:
    extra_validation:
    - clientlib_dependency_graph_clear
    - publish_clientlib_minification_enabled
  headless:
    extra_validation:
    - initial_document_stylesheet_present
    - css_asset_manifest_verified
source_prs:
- GoogleChromeLabs/llaminator#37
- martincostello/costellobot#471
- martincostello/dependabot-helper#513
- martincostello/website#1321
- y-scope/yscope-log-viewer#41
- ipfs-shipyard/helia-service-worker-gateway#112
---
# Stylesheet delivery

> **Risk tier:** medium · **Applies to:** CS, Headless

## What this addresses

The evidence shows projects adopting CSS minification, extracting CSS into emitted assets, linking generated CSS files from layouts, and ensuring CSS imports are retained during production builds. It also shows that incorrectly marking CSS as side-effect-free can cause CSS to be omitted from final assets.

## When to apply / when to skip
**Apply when:**
- The audited page loads required CSS through JavaScript runtime injection rather than an initial-document stylesheet.
- A CSS bundle is materially oversized, contains avoidable whitespace or comments, or includes selectors for unrelated page experiences.
- The emitted stylesheet order, chunk ownership, and initial-page CSS path are statically traceable.
- The page can retain all layout-critical CSS before first render after extraction or bundle changes.

**Skip when:**
- The candidate stylesheet contains dynamic styles required before a client-rendered component can mount and its load order cannot be verified.
- CSS is intentionally deferred because it styles only below-the-fold or interaction-only UI.
- Splitting the stylesheet would move required above-the-fold selectors into an asynchronous chunk.
- The CS clientlib dependency or embed graph is not fully traced.
- The audit identifies another dominant performance issue that should be addressed first.

## Recommended approaches

### CS: publish a scoped, minified clientlib stylesheet from the initial HTML

Keep common and template-specific CSS in separate clientlib categories, include only the category needed by the page template, and render the stylesheet through the standard HTL clientlib template.

```xml
<!-- Good: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/site-base/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.site.base]"
          allowProxy="{Boolean}true"/>

<!-- ui.apps/src/main/content/jcr_root/apps/example/clientlibs/site-article/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.site.article]"
          dependencies="[example.site.base]"
          allowProxy="{Boolean}true"/>
```

```text
# Good: clientlibs/site-article/css.txt
article.css
```

```html
<!-- Good: page component HTL renders CSS before body content -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.css @ categories='example.site.article'}"/>
```

Ensure the served CSS asset is minified and verify the emitted asset after the change.

### Headless: link the emitted CSS asset in the initial application document

For a headless application consuming AEM Content Fragments or GraphQL data, make the build-produced stylesheet available in the initial HTML shell and keep above-the-fold rules in that initial asset.

```html
<!-- Good: application document served before AEM content is hydrated -->
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/assets/site.4a91c2.css">
</head>
<body>
  <main id="app">
    <article class="article-shell">
      <h1>Loading article…</h1>
    </article>
  </main>
  <script src="/assets/app.4a91c2.js" defer></script>
</body>
```

```css
/* Good: emitted site CSS retains layout-critical shell styles */
.article-shell {
  max-width: 72rem;
  margin: 0 auto;
  padding: 1rem;
}
```

The evidence includes projects updating layouts to reference generated CSS assets and configuring `mini-css-extract-plugin` to emit CSS files. Content-specific CSS may be split into later chunks only when it cannot affect the initial viewport or layout reservation.

### Remove unused framework and component CSS from the initial bundle

Move CSS for optional components into the clientlib category or application chunk that owns that component, while retaining shared tokens and layout primitives in the initial stylesheet.

```xml
<!-- Good: carousel CSS is not part of the global site category -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.component.carousel]"
          dependencies="[example.site.base]"
          allowProxy="{Boolean}true"/>
```

```text
# Good: clientlibs/component-carousel/css.txt
carousel.css
```

```html
<!-- Good: only templates that render the carousel include its CSS category -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.css @ categories='example.site.base'}"/>
<sly data-sly-test="${properties.enableCarousel}">
  <sly data-sly-call="${clientlib.css @ categories='example.component.carousel'}"/>
</sly>
```

One source PR reported reducing a generated `bootstrap.min.css` asset from 1,021,580 bytes to 233,399 bytes while optimizing bundle configuration. Preserve dependency order so component rules continue to override shared base rules where required.

## Anti-patterns

### Injecting required CSS after JavaScript starts

```javascript
// Bad: required page styling is created only after JavaScript executes
const stylesheet = document.createElement('link');
stylesheet.rel = 'stylesheet';
stylesheet.href = '/etc.clientlibs/example/clientlibs/site-article.css';
document.head.appendChild(stylesheet);
```

**Why this is bad:** The evidence describes `css-loader` loading CSS as a string and `style-loader` injecting it at runtime. It also reports approximately 3 KiB of uncompressed bundle overhead from that injection approach in one project.

### Putting every component stylesheet in the global CS clientlib

```xml
<!-- Bad: every page downloads CSS for components it cannot render -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.site]"
          embed="[example.site.base,
                  example.component.carousel,
                  example.component.accordion,
                  example.component.search,
                  example.component.forms,
                  example.component.video]"/>
```

```html
<!-- Bad: included on every template -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.css @ categories='example.site'}"/>
```

**Why this is bad:** The provided evidence supports minimizing and reducing generated CSS bundle size, but does not specifically evaluate AEM clientlib embedding behavior. Validate the emitted CSS inventory and size before and after changing clientlib composition.

### Extracting CSS into an asynchronous chunk that styles the initial viewport

```html
<!-- Bad: initial HTML has no stylesheet for the visible article shell -->
<body>
  <main class="article-shell">
    <h1>Article title</h1>
  </main>
  <script src="/assets/app.js" defer></script>
</body>
```

```javascript
// Bad: the initial viewport is styled only after an asynchronous feature load
function startArticle() {
  const stylesheet = document.createElement('link');
  stylesheet.rel = 'stylesheet';
  stylesheet.href = '/assets/article-styles.css';

  stylesheet.addEventListener('load', () => {
    document.documentElement.classList.add('article-ready');
  });

  document.head.appendChild(stylesheet);
}

window.setTimeout(startArticle, 0);
```

**Why this is bad:** The evidence supports extracting CSS into emitted files and linking generated CSS from application layouts, but does not provide a measured result for asynchronous CSS that styles the initial viewport. Verify the initial document’s stylesheet references and the resulting render path.

### Marking CSS as side-effect-free so the build drops it

```text
# Bad: clientlibs/site-article/css.txt omits article.css from the published clientlib
base.css
```

```css
/* article.css exists in the clientlib folder but is never included in css.txt */
.article-shell {
  max-width: 72rem;
  margin: 0 auto;
  padding: 1rem;
}
```

**Why this is bad:** One source PR reports that CSS files were ignored during tree splitting when the package declared no side effects. That project changed `sideEffects` to include `"*.css"` and added a test verifying that the expected CSS file was present in the distribution output.

## Flavor-specific notes

### CS

Trace the clientlib `dependencies`, `embed` relationships, and every HTL template that includes the affected category before splitting or removing CSS. Preserve the existing cascade order: base tokens and grid/layout CSS should remain before template and component categories.

Confirm the publish-tier clientlib configuration produces minified output and verify the generated `.css` asset size after the change rather than relying only on source-file size.

### Headless

Verify that the HTML shell references the emitted, cache-busted CSS filename and that deployment publishes the matching asset before changing chunk names or extraction behavior.

For client-rendered applications, verify that shell and visible-component CSS are present in the initial stylesheet when required. Verify that CSS imports remain included in production output rather than being removed by side-effect optimization.