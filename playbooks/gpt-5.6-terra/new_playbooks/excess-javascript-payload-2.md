---
issue_type: excess-javascript-payload-2
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
required_validation: []
forbidden_techniques: []
source_prs:
- codesquad-members-2022/todo-list#175
- duckduckgo/duckduckgo-privacy-extension#1812
- epfml/disco#652
- aws-observability/aws-rum-web#563
---
# Excess JavaScript payload 2

> **Risk tier:** medium · **Applies to:** EDS, CS, Headless · **CWV metric:** LCP, INP

## What this addresses

CommonJS-transformed or mixed-module dependencies can prevent browser-build tooling from statically removing unused exports. Preserving ESM through the browser bundle pipeline can restore tree shaking and reduce the emitted browser bundle size.

## When to apply / when to skip
**Apply when:**
- Bundle analysis identifies a dependency whose unused exports are included in a page-critical JavaScript payload.
- Source modules use ESM but a compiler or compatibility transform converts `import` or `export` to CommonJS before the browser bundle is tree-shaken.
- The supported-browser baseline is known for the affected bundle.
- CommonJS-only dependencies and their interop paths have been traced and tested.
- For CS or AMS, the affected JavaScript can be split into a feature-scoped clientlib without changing known template or component dependencies.

**Do not apply when:**
- The identified JavaScript is already an ESM-preserving, tree-shaken output with no meaningful unused-code reduction available.
- The dependency is CommonJS-only and replacing or wrapping it would change runtime behavior beyond the scoped fix.
- The candidate is a shared global bundle whose consumers and compatibility requirements are not fully known.
- Splitting a clientlib would cause duplicated delivery, break dependency ordering, or require changes outside the verified affected pages.

## Recommended approaches

### Preserve ESM in EDS block code

Keep block dependencies as static ESM imports so the delivery pipeline can identify which exports are used. Import only the named helper needed by the block rather than loading a CommonJS utility object.

```javascript
// Good — blocks/product-card/product-card.js
import { formatPrice } from './product-utils.js';

export default function decorate(block) {
  const price = block.querySelector('[data-product-price]');

  if (price) {
    price.textContent = formatPrice(price.textContent);
  }
}
```

```javascript
// Good — blocks/product-card/product-utils.js
export function formatPrice(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(Number(value));
}

export function formatInventoryCount(value) {
  return `${value} items available`;
}
```

Static named ESM imports make the used export explicit and can allow downstream tooling to omit unused exports.

### Scope CS or AMS browser artifacts with a clientlib

For CS or AMS, optimize the browser artifact before placing it in a clientlib. Keep the resulting feature artifact in a narrowly scoped category and include that category only where the feature is rendered. A clientlib split is a medium-risk change because category dependencies and template inclusions must be traced before it is applied.

```xml
<!-- Good — ui.apps/.../clientlibs/clientlib-product-card/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.product-card]"
          dependencies="[site.base]"/>
```

```text
# Good — ui.apps/.../clientlibs/clientlib-product-card/js.txt
product-card.min.js
```

```html
<!-- Good — product-card.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-use.product="com.example.core.models.ProductCard"/>
<sly data-sly-test="${product.enabled}">
  <sly data-sly-call="${clientlib.js @ categories='site.product-card'}"/>
  <div class="product-card" data-product-id="${product.id}"></div>
</sly>
```

Ensure the upstream browser build preserves static ESM imports until its optimization step runs. The emitted file listed in `js.txt` should be produced after unused exports have been removed.

### Verify headless application bundle boundaries

For a headless implementation, apply the change to the browser application bundle that renders AEM-delivered content. Keep static imports for page- or component-specific code.

Confirm that the production browser artifact no longer contains the unused dependency exports and that CommonJS-only SDKs or browser compatibility shims continue to work for the supported browser baseline.

## Anti-patterns

### Loading a CommonJS utility namespace for one helper

```javascript
// Bad — blocks/product-card/product-card.js
import * as productUtils from './product-utils.js';

export default function decorate(block) {
  const price = block.querySelector('[data-product-price]');

  if (price) {
    price.textContent = productUtils.formatPrice(price.textContent);
  }
}
```

**Why this is bad:** Transforming ESM module syntax to CommonJS can prevent tree shaking from removing unused exports.

### Including a feature clientlib from the global page template

```html
<!-- Bad — base-page.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.js @ categories='site.product-card'}"/>
```

**Why this is bad:** Review whether the feature artifact is needed on every page that includes the shared template.

## Flavor-specific notes

### EDS

Preserve static `import` and `export` syntax in the code that is passed to the browser optimization pipeline. Do not replace a named import with `require()` merely to share utilities; keep shared helpers in an ESM file and import only the exports used by the block.

Confirm that the affected block is actually loaded on the audited page before changing it. A payload reduction in an unvisited block does not address the attributed CWV issue.

### CS and AMS

Verify that the frontend build producing the clientlib artifact preserves ESM until optimization runs, then confirm the emitted artifact no longer contains the unused dependency exports.

Before changing a category dependency or inclusion, trace all templates and clientlibs that include or embed it.

### Headless

Apply this only to the browser application bundle that renders the AEM headless response. Preserve ESM through that application's production optimization stage, and verify that any CommonJS-only SDKs or browser compatibility shims still work for the supported browser baseline.

Do not change server-side rendering, API client behavior, or content-model contracts solely to change module format; this playbook is limited to verified browser-payload elimination.