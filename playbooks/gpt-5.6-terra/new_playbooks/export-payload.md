---
issue_type: export-payload
applicable_flavors:
- eds
- cs
- headless
risk_tier: high
required_validation:
- modern_javascript_build_pipeline_confirmed
- production_bundle_export_usage_traced
- module_side_effects_audited
- dynamic_import_and_namespace_usage_audited
- generated_client_artifacts_compared
- application_regression_suite_passed
forbidden_techniques: []
source_prs:
- vercel/turbo#3338
- vercel/turbo#7986
- vercel/turbo#8523
- vercel/next.js#70017
- vercel/next.js#70114
---
# Export payload

> **Risk tier:** high · **Applies to:** EDS, CS, headless

## What this addresses

Tree shaking can split ECMAScript modules into parts representing module evaluation and individual exports. In the cited Turbopack/Next.js changes, tree shaking is enabled for production builds using module fragments, while development uses a re-exports-only mode.

This is recommendation-only because module evaluation can be required even when exports are unused, and some exports may need to be retained for framework or runtime conventions.

## When to apply / when to skip
**Apply when:**
- A modern production JavaScript build pipeline is confirmed to process the page or application entry modules before deployment.
- Production bundle analysis identifies reachable modules or barrel exports whose individual exports are unused by the relevant entry point.
- Module-level side effects, namespace imports, dynamic property access, and dynamic imports have been traced.
- The application has regression coverage for the affected page templates, blocks, or client-rendered routes.
- A production artifact comparison can verify the effect of the change on emitted client artifacts and runtime behavior.

**Skip when:**
- JavaScript is served as unbundled clientlib files or raw EDS block files without a verified tree-shaking step.
- The module performs required work at evaluation time, such as registering a browser event handler, defining a custom element, or initializing a required integration.
- Consumers access exports dynamically, for example through `module[featureName]`, `import()`, or a namespace object.
- The affected package has unknown side-effect semantics or is shared by unrelated application entry points.
- The change cannot be validated with production-build artifact inspection and application-level regression testing.

## Recommended approaches

### Import the specific EDS block helper that the block uses

Keep block dependencies explicit so a production ESM build can identify the helper used by `decorate(block)` separately from other exports.

```javascript
// Good — blocks/hero/hero.js
import { createOptimizedPicture } from '../../scripts/aem.js';

export default function decorate(block) {
  const image = block.querySelector('picture img');

  if (!image) return;

  const optimizedPicture = createOptimizedPicture(
    image.src,
    image.alt,
    false,
    [{ width: '750' }, { width: '1200' }],
  );

  image.closest('picture').replaceWith(optimizedPicture);
}
```

```javascript
// Good — scripts/aem.js
export function createOptimizedPicture(src, alt, eager, breakpoints) {
  // Shared responsive-image implementation.
}

export function toClassName(value) {
  return value.toLowerCase().replace(/\s+/g, '-');
}

export function decorateIcons(element) {
  // Icon decoration used by other blocks.
}
```

A named import provides an explicit import of `createOptimizedPicture`. Where the deployed project has a verified production tree-shaking stage, validate whether unrelated exports are excluded from emitted artifacts.

### Isolate required module side effects from reusable exports

Move deliberate initialization into an explicit function, and call it from the application entry point that requires it. This makes the required setup explicit and separates it from other exports.

```javascript
// Good — clientlib-site/src/site-init.js
export function initializeSiteInteractions() {
  document.documentElement.classList.add('js-ready');

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-disclosure-trigger]');
    if (trigger) trigger.closest('[data-disclosure]').classList.toggle('is-open');
  });
}

export function formatPrice(value, locale, currency) {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
  }).format(value);
}
```

```javascript
// Good — clientlib-site/src/main.js
import { initializeSiteInteractions } from './site-init.js';

initializeSiteInteractions();
```

```xml
<!-- Good — ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/clientlib-site/.content.xml -->
<jcr:root jcr:primaryType="cq:ClientLibraryFolder"
          categories="[acme.site]"
          dependencies="[acme.base]"
          allowProxy="{Boolean}true"/>
```

```text
# Good — ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/clientlib-site/js.txt
dist/main.js
```

```html
<!-- Good — page component HTL includes the clientlib category -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='acme.site'}"/>
```

Confirm that the clientlib contains build output from a verified tree-shaking-capable pipeline before expecting export-level removal.

### Keep headless route entries narrow and use explicit named exports

For a client-rendered headless implementation, have each route entry import only the AEM content adapter and rendering helpers it needs.

```javascript
// Good — client/routes/product-detail.js
import { getProductByPath } from '../aem/content-fragments.js';
import { renderProductGallery } from '../components/product-gallery.js';

export async function decorateProductDetail(container, productPath) {
  const product = await getProductByPath(productPath);

  container.querySelector('[data-product-title]').textContent = product.title;
  renderProductGallery(container.querySelector('[data-product-gallery]'), product.images);
}
```

```javascript
// Good — client/aem/content-fragments.js
export async function getProductByPath(path) {
  const response = await fetch(`/api/products?path=${encodeURIComponent(path)}`);

  if (!response.ok) throw new Error(`Unable to load product: ${response.status}`);
  return response.json();
}

export async function getRelatedProducts(productId) {
  const response = await fetch(`/api/related-products?id=${encodeURIComponent(productId)}`);

  if (!response.ok) throw new Error(`Unable to load related products: ${response.status}`);
  return response.json();
}
```

Named imports make the route’s direct dependencies explicit. Compare the production route chunk before and after the change, and verify navigation, error handling, and content-fragment rendering.

## Anti-patterns

### Hiding required initialization in module evaluation

```javascript
// Bad — clientlib-site/src/analytics.js
window.dataLayer = window.dataLayer || [];
window.dataLayer.push({ event: 'site-client-loaded' });

export function trackSearch(query) {
  window.dataLayer.push({ event: 'search', query });
}
```

```javascript
// Bad — clientlib-site/src/main.js
import { initializeSiteInteractions } from './site-init.js';

initializeSiteInteractions();
```

**Why this is bad:** The tree-shaking implementation distinguishes module evaluation from individual exports. If this module’s evaluation is required, its side effects must be preserved even when `trackSearch` is not imported.

### Dynamic export access

```javascript
// Bad — blocks/product/product.js
import * as productFeatures from './product-features.js';

export default function decorate(block) {
  const featureName = block.dataset.feature;
  productFeatures[featureName](block);
}
```

**Why this is bad:** The selected export is determined at runtime rather than named in the import. Audit this pattern and validate the emitted artifact and runtime behavior before relying on export-level removal.

## Flavor-specific notes

### EDS

Do not assume that block-relative imports alone result in unused-export removal. Confirm that the project’s production deployment path applies tree shaking to the relevant `blocks/` and `scripts/` modules before recommending export removal.

Do not remove helpers solely because the current block does not import them: another block may import the shared helper directly. Trace relevant imports and validate affected decorated pages.

```javascript
// Good — keep the lazy block boundary explicit
export default function decorate(block) {
  const observer = new IntersectionObserver(async ([entry]) => {
    if (!entry.isIntersecting) return;

    const { initializeProductRecommendations } =
      await import('./product-recommendations.js');

    initializeProductRecommendations(block);
    observer.disconnect();
  });

  observer.observe(block);
}
```

### CS

Apply this guidance only when clientlib JavaScript is generated by a verified modern build step before it is placed in the clientlib folder.

Trace categories, dependencies, and template includes before changing entry modules. A shared category may serve multiple page templates, so an export unused on one template may still be required by another.

```html
<!-- Good — scope a feature category to templates that require it -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='acme.product'}"/>
```

### Headless

Headless applications can use production ESM builds that perform tree shaking. Validate each affected route chunk rather than relying only on an application-wide bundle total, and test AEM content loading, route transitions, and runtime-selected component mappings after any export-surface change.