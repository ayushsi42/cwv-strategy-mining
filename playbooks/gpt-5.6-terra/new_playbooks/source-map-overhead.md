---
issue_type: source-map-overhead
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- Confirm which deployed production JavaScript artifacts contain inline source maps,
  source-map references, or publicly reachable map files.
- Confirm the production build or release stage that creates each browser-facing artifact.
- Confirm whether source maps are needed outside local development and, if so, how
  they are retained.
- Confirm that deployed JavaScript has no stale source-map reference after map publication
  is disabled.
- Confirm that public asset paths do not serve matching `.map` files when maps are
  intended to remain private.
forbidden_techniques: []
flavor_overrides:
  eds:
    extra_validation:
    - Inspect the JavaScript artifact served by the EDS delivery origin rather than
      only repository source files.
  cs:
    extra_validation:
    - Trace the clientlib and any frontend build stages that produce the publish-facing
      JavaScript artifact.
    - Verify that proxy-served clientlib paths do not expose source-map files.
  ams:
    extra_validation:
    - Trace the clientlib and custom static-asset build stages that produce publish-facing
      JavaScript.
    - Verify Dispatcher and CDN rules do not expose source-map files.
  headless:
    extra_validation:
    - Trace the production browser-application build and deployment pipeline separately
      from AEM API delivery.
source_prs:
- aduros/wasm4#64
- Beardless-sheik/To-do-list#6
- software-mansion/react-native-reanimated#3655
- woowacourse-teams/2023-stamp-crush#679
---
# Source map overhead

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** LCP, INP

## What this addresses

Production JavaScript can contain inline source maps or retain `sourceMappingURL` references to deployed `.map` files. Source maps can increase bundle size; one reported web build increased from 27.6 kB without source maps to 225 kB with them. Source maps may be useful for debugging, but release and debug builds can use different source-map settings.

Change only the production delivery profile after confirming that the required debugging workflow is preserved.

## When to apply / when to skip
**Apply when:**
- The production JavaScript inventory identifies inline `sourceMappingURL=data:` content.
- Production JavaScript retains references to `.map` files that are publicly reachable from publish, CDN, EDS, or the headless application's production origin.
- The affected artifact is served to end users and the production build profile can be changed independently from local development builds.
- Source maps are not required in the browser-facing production artifact.

**Skip when:**
- The artifact inventory cannot distinguish production bundles from development or preview builds.
- Removing map files would leave `sourceMappingURL` comments in deployed JavaScript.
- The candidate is an authored source file rather than a generated production artifact.

## Recommended approaches

### Disable source-map publication for the production release artifact

Keep source maps available for local development where needed. Configure the production stage that publishes browser-facing JavaScript to omit inline source-map payloads, public map files, and source-map references.

For EDS, source-map behavior belongs in the deployment or artifact-generation process, not in block initialization code.

```javascript
// Good: blocks/product/product.js
// Keep EDS source readable for local development. The production artifact
// pipeline determines whether source maps are generated or published.
export default function decorate(block) {
  const button = block.querySelector('a');

  button?.addEventListener('click', () => {
    block.classList.toggle('product-expanded');
  });
}
```

Verify the deployed JavaScript artifact does not append an inline `sourceMappingURL=data:` comment and does not reference a publicly served `.map` file.

### Keep AEM clientlib definitions separate from source-map handling

For CS and AMS clientlibs, retain normal clientlib structure and configure the release compilation or frontend build stage—not component markup—to control source-map publication.

```xml
<!-- Good: ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/clientlib-product/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[acme.product]"
          dependencies="[acme.site.base]"
          allowProxy="{Boolean}true"/>
```

```text
# Good: ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/clientlib-product/js.txt
product.js
```

```html
<!-- Good: product.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='acme.product'}"></sly>
```

The clientlib category and HTL inclusion remain unchanged. Apply the source-map change only to the production stage that creates the JavaScript served through the clientlib path.

### Retain maps outside the browser-facing artifact when needed

When source maps are needed for debugging, generate or retain them separately from the browser-facing JavaScript artifact. Publish only the JavaScript artifact without an inline source-map payload or a public source-map reference.

For headless implementations, apply this to the browser application's production bundle rather than to AEM JSON responses or Sling Model exports. Keep application script URLs versioned normally while ensuring the delivered JavaScript does not contain inline maps or refer to publicly deployed `.map` files.

## Anti-patterns

### Inline source map in a deployed JavaScript artifact

```javascript
// Bad: deployed EDS block or clientlib artifact contains an inline map.
export default function decorate(block) {
  block.ownerDocument.documentElement.classList.add('js-ready');
}
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbInByb2R1Y3QuanMiXSwibWFwcGluZ3MiOiJBQUFBIn0=
```

**Why this is bad:** The source-map payload is included in the JavaScript artifact and can increase its size.

### Publishing a map file with a production JavaScript reference

```javascript
// Bad: the production artifact directs browser tooling to a public map file.
export default function decorate(block) {
  block.classList.add('is-ready');
}
//# sourceMappingURL=product.js.map
```

**Why this is bad:** This associates the deployed bundle with a public source-map artifact. If maps are not intended for public delivery, keep them out of the published asset path.

### Deleting `.map` files while retaining the source-map reference

```javascript
// Bad: the map file was removed, but the deployed JavaScript still references it.
export default function decorate(block) {
  block.classList.add('is-ready');
}
//# sourceMappingURL=product.js.map
```

**Why this is bad:** The deployed JavaScript still declares a source-map reference after the corresponding map has been removed.

### Disabling maps for every environment

```text
# Bad: source-map generation and retention are removed from local, test,
# and production workflows without preserving a debugging path.
source maps: disabled everywhere
```

**Why this is bad:** Source maps can be useful for debugging. Release and debug builds can use different source-map settings, so public production delivery can be changed without necessarily disabling maps in every environment.

## Flavor-specific notes

### EDS

EDS block source files should remain normal block modules with `decorate(block)` exports. Source-map behavior belongs in the deployment or artifact-generation configuration rather than in block initialization logic.

```javascript
// Good: blocks/carousel/carousel.js
export default function decorate(block) {
  const observer = new IntersectionObserver((entries) => {
    if (!entries[0].isIntersecting) return;

    import('./carousel-runtime.js').then(({ initializeCarousel }) => {
      initializeCarousel(block);
      observer.disconnect();
    });
  });

  observer.observe(block);
}
```

Inspect the deployed block JavaScript returned by the EDS delivery origin, not only the repository source file. Confirm that the delivered artifact has neither an inline `sourceMappingURL=data:` comment nor a public `.map` sibling before declaring the fix complete.

### CS

Trace the clientlib compilation path before changing it. AEM clientlibs may be assembled by the standard clientlib pipeline, a frontend module build, or both; change only the production stage that creates the browser-facing artifact.

Keep source-map artifacts out of `ui.apps` packages and proxy-served clientlib paths when they are not intended for public delivery. If source maps are retained separately, ensure they are not reachable through `/etc.clientlibs/` or any CDN origin serving publish assets.

### AMS

In addition to tracing the clientlib compiler, inspect Dispatcher rules and cached static-asset paths. A map file can remain publicly available through Dispatcher or CDN cache after the JavaScript build stops generating new maps.

AMS applications can have legacy clientlibs and custom build steps in the same release. Inventory both `/etc.clientlibs/` output and custom static bundles before removing maps so a legacy bundle does not retain a stale `sourceMappingURL` comment.

### Headless

For headless delivery, apply the change to the browser application's production bundle rather than to AEM JSON responses or Sling Model exports. Keep production API payloads and application script URLs versioned normally, but ensure the browser-delivered JavaScript does not include inline maps or refer to publicly deployed `.map` files.

If maps are retained for debugging, keep that retained map archive outside the application's public asset origin.