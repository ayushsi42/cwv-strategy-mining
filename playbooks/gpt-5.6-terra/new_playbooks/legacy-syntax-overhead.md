---
issue_type: legacy-syntax-overhead
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- Confirm the approved supported-browser baseline before changing a production JavaScript
  target.
- Trace any legacy-browser commitments and identify whether a separate legacy delivery
  path is required.
- Inventory deployed production JavaScript for downlevel transforms, helpers, and
  runtime polyfills.
- Compare deployed modern-target and legacy-target bundle output, including transfer
  size and parse cost where available.
- Verify whether runtime polyfills are still required by the approved browser baseline.
forbidden_techniques:
- pattern: '"target"\s*:\s*"es(?:3|5|6|2015)"'
  reason: Don't lower the production JavaScript target to ES3/ES5/ES6 without a supported-browser
    requirement; lower targets can require additional transpilation and increase bundle
    size
- pattern: '@babel/plugin-transform-regenerator'
  reason: Don't add the regenerator transform to the primary browser bundle unless
    the approved browser baseline requires it; validate the generated output and any
    required runtime support
flavor_overrides:
  eds:
    extra_validation:
    - Confirm that deployed EDS block JavaScript preserves the approved browser baseline.
  cs:
    extra_validation:
    - Verify that the clientlib pipeline preserves approved modern syntax in published
      output.
    - Trace all templates and components that consume a changed clientlib category.
  ams:
    extra_validation:
    - Verify that custom clientlib or frontend build steps preserve approved modern
      syntax.
    - Confirm any legacy-browser support commitment before changing a shared clientlib
      target.
  headless:
    extra_validation:
    - Verify the browser target of the deployed client hydration bundle.
    - Confirm that any required legacy delivery path is separately maintained and
      tested.
source_prs:
- ant-design/ant-design#53390
- teetee971/akiprisaye-web#2110
- saddle-finance/saddle-frontend#879
- TanStack/query#5597
- aws-amplify/amplify-js#12365
- PalisadoesFoundation/talawa-admin#3605
---
# Legacy syntax overhead

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless

## What this addresses

A lower JavaScript target can require additional transpilation and compatibility code. Raising the production target to an approved modern browser baseline can reduce bundle size by requiring less transpilation. Validate deployed output to determine whether this also changes parse or execution work.

## When to apply / when to skip
**Apply when:**
- The production JavaScript output contains legacy transforms, compatibility helpers, or polyfills attributable to an older JavaScript target.
- The supported-browser baseline is documented and confirms that the intended modern syntax is available.
- A production bundle comparison shows that the modern target removes meaningful bytes or parse work.
- Legacy-browser support, if still required, can be delivered through a separately maintained legacy path.

**Skip when:**
- The site has a contractual requirement to support browsers below the approved modern baseline.
- The AEM client-library pipeline, CDN transformation layer, or headless deployment pipeline cannot be verified to preserve the intended output.
- The suspected overhead is third-party code that the site does not build or control.
- Raising the target would change syntax in a shared clientlib without tracing every consuming template.

## Recommended approaches

### Serve modern syntax from an EDS block

```javascript
// Good — preserve the required EDS block entry-point signature.
export default function decorate(block) {
  const trigger = block.querySelector('button');
  const status = block.querySelector('[data-status]');

  trigger?.addEventListener('click', async () => {
    const { getAvailability } = await import('./availability.js');
    const result = await getAvailability(block.dataset.sku);

    if (status) {
      status.textContent = result?.message ?? 'Availability unavailable';
    }
  });
}
```

Confirm the EDS browser baseline before shipping syntax that is not supported by it, and inspect the deployed output for any transforms or polyfills added by the build process.

### Keep CS/AMS clientlib source modern and scope it to the component

```xml
<!-- Good — jcr_root/apps/site/clientlibs/product-card/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.product-card]"
          dependencies="[site.base]"/>
```

```html
<!-- Good — product-card.html -->
<sly data-sly-use.card="com.site.core.models.ProductCard"/>
<div class="product-card" data-sku="${card.sku}">
  <button class="product-card__availability" type="button">
    Check availability
  </button>
  <p class="product-card__status" data-status></p>
</div>
```

```javascript
// Good — clientlibs/product-card/js/product-card.js
document.querySelectorAll('.product-card').forEach((card) => {
  const button = card.querySelector('.product-card__availability');
  const status = card.querySelector('[data-status]');

  button?.addEventListener('click', async () => {
    const response = await fetch(`/api/availability.${card.dataset.sku}.json`);
    const availability = await response.json();

    if (status) {
      status.textContent = availability?.message ?? 'Unavailable';
    }
  });
});
```

Keep the clientlib category limited to templates that render the component, and configure the project build and minification steps to preserve syntax supported by the approved browser baseline. Compare resulting bundles to determine whether downlevel transforms or helpers were removed.

### Raise the headless client target only after verifying delivered output

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "lib": ["DOM", "ES2020"]
  }
}
```

```javascript
// Good — code used by the deployed headless client after verifying its modern build
export async function loadFragment(path) {
  const response = await fetch(`${path}.model.json`);
  const model = await response.json();

  return model?.items ?? [];
}
```

A modern target can retain language features that would otherwise be transpiled. Verify the deployed hydration bundle rather than relying only on source configuration, because a downstream build or CDN process may still transpile it.

## Anti-patterns

### Downleveling the primary production bundle to ES5

```json
{
  "compilerOptions": {
    "target": "es5",
    "module": "esnext"
  }
}
```

**Why this is bad:** An ES5 target can require transpilation of modern application syntax. Compare the resulting output with an approved modern target to identify any bundle-size increase.

### Adding regenerator transforms to a modern browser bundle

```javascript
// Bad — adds a regenerator transform to the primary bundle without validating need
module.exports = {
  plugins: [
    '@babel/plugin-transform-regenerator',
  ],
};
```

**Why this is bad:** This transform should be included only when required by the approved browser baseline. Validate its generated output and any runtime dependencies against a build that preserves native async support.

### Shipping one legacy-transformed clientlib to every template

```xml
<!-- Bad: global category makes every page receive legacy compatibility code -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.base]"
          dependencies="[site.legacy-polyfills,site.product-card]"/>
```

```html
<!-- Bad: included by the shared page head for all templates -->
<sly data-sly-call="${clientlib.all @ categories='site.base'}"/>
```

**Why this is bad:** A global clientlib can cause pages that do not use a feature to receive its code. Confirm the delivered assets and scope compatibility code only where a validated requirement exists.

### Removing compatibility code without separating a required legacy path

```javascript
// Bad — assumes every visitor supports native optional chaining without validation
const message = window.siteConfig.checkout.message?.trim() ?? '';
```

**Why this is bad:** Removing compatibility support from the only delivered bundle can break users covered by an existing legacy-browser commitment. Confirm the approved browser baseline or provide and test a separate legacy path.

## Flavor-specific notes

### EDS

Avoid introducing a transpilation step solely for older browsers without confirming the supported-browser baseline. Retain the required block entry-point signature and inspect deployed block JavaScript to determine whether a shared build process injected compatibility code.

### CS

For AEM as a Cloud Service, trace the clientlib category from `.content.xml` through the HTL template before changing its syntax target. Validate published output and scope component code to the categories that consume it.

### AMS

Legacy AMS projects can have custom Maven, frontend, or clientlib build steps. Identify the pipeline and any browser-support commitment before changing the target, especially where a shared `site.base` clientlib is embedded by older templates.

### Headless

Validate the browser target of the deployed client-rendered application independently of AEM content delivery. If legacy support remains necessary, use an explicitly tested separate legacy delivery path rather than applying legacy transforms to all clients.