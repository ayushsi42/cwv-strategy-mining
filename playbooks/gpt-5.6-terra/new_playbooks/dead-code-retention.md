---
issue_type: dead-code-retention
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
required_validation:
- unused_initializer_and_export_graph_traced
- initializer_side_effects_proven_absent
- production_bundle_tree_shaking_verified
- retained_export_runtime_paths_tested
- purity_comments_survive_production_transform
forbidden_techniques:
- pattern: \btsc\b[^\r\n]*--removeComments\b
  reason: Don't remove comments in the production TypeScript emit — it can strip /*#__PURE__*/
    annotations before the bundler can tree-shake the unused initializer
flavor_overrides:
  eds:
    extra_validation:
    - block_dependency_graph_traced
  cs:
    extra_validation:
    - clientlib_category_and_minifier_traced
  headless:
    extra_validation:
    - client_entry_chunk_traced
source_prs:
- iTowns/itowns#2608
- vercel/next.js#34687
- mrdoob/three.js#24221
- salesforce/lwc#3520
- wagmi-dev/viem#687
- web-infra-dev/rspack#4655
- samchon/typia#928
- Effect-TS/effect#3296
- thirdweb-dev/js#4179
- vitejs/vite#19189
- rolldown/rolldown#3812
---
# Dead-code retention

> **Risk tier:** medium · **Applies to:** EDS, CS, headless · **CWV metric:** LCP, INP

## What this addresses

Bundlers may retain module-scope function calls, constructors, and generated values when they cannot prove that evaluating them has no side effects. Adding a `/*#__PURE__*/` annotation to a verified side-effect-free initializer can let the production bundler remove it when its export is unused.

For AEM CS/AMS clientlibs, verify how JavaScript is delivered and whether the configured build path performs module-level tree-shaking. Where it does not, scope feature code to only the pages that require it.

## When to apply / when to skip
**Apply when:**
- Bundle analysis identifies an unused module export whose module-scope initializer is retained in a browser bundle.
- The initializer is limited to deterministic value construction, such as a lookup table, formatter definition, `Map`, `Set`, `TextEncoder`, or parsing a known-valid compile-time JSON string.
- The annotation survives the production transform and the resulting browser bundle removes the unused expression.
- Runtime tests cover every retained export that could depend on the initialized value.
- For CS/AMS, a clientlib category contains code that is included by pages that do not require the feature.

**Skip when:**
- The initializer registers an event listener, custom element, analytics integration, global value, polyfill, service worker behavior, or other observable side effect.
- The initializer mutates a shared object, reads mutable global state, or depends on initialization order.
- The candidate is used for required module registration even when its local variable appears unused.
- The production build removes purity comments before tree-shaking, and preserving them cannot be verified in the current build path.
- A CS/AMS clientlib is already scoped to only the templates and components that require it.

## Recommended approaches

### Annotate a verified pure module-scope value

Mark the call or constructor expression, not the declaration, when constructing a value has no observable behavior and the value can be discarded if its export is unused.

```javascript
// Good — blocks/hero/formatters.js
function createHeroFormatter() {
  return {
    normalizeTitle(value) {
      return value.trim().replace(/\s+/g, ' ');
    },
  };
}

// This formatter is removable when no consumer imports it.
export const heroFormatter = /*#__PURE__*/ createHeroFormatter();
```

```javascript
// Good — blocks/hero/hero.js
import { heroFormatter } from './formatters.js';

export default function decorate(block) {
  const observer = new IntersectionObserver(async (entries) => {
    if (!entries[0].isIntersecting) return;

    const { enhanceHero } = await import('./enhance-hero.js');
    enhanceHero(block, heroFormatter);
    observer.disconnect();
  });

  observer.observe(block);
}
```

The annotation provides purity metadata for `createHeroFormatter()`. Verify that the formatter remains available whenever `heroFormatter` is imported by the block.

### Split a CS/AMS clientlib by feature scope

Create a dedicated clientlib category for code that is needed only by a specific feature or template. This can prevent unrelated pages from receiving the feature code.

```xml
<!-- Good — ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/site-search/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[acme.site-search]"
          dependencies="[acme.site-base]"
          allowProxy="{Boolean}true"/>
```

```text
# Good — ui.apps/src/main/content/jcr_root/apps/acme/clientlibs/site-search/js.txt
#base=js
search.js
```

```html
<!-- Good — search-page.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-use.searchModel="com.acme.site.core.models.SearchModel"/>
<sly data-sly-call="${clientlib.js @ categories='acme.site-search'}"></sly>

<section class="search" data-search-endpoint="${searchModel.endpoint}">
  <h1>${searchModel.title}</h1>
</section>
```

Treat this as a medium-risk change: trace category dependencies and every template inclusion before moving code. Validate that the feature still receives its required clientlib on publish.

### Annotate generated JSON parsing when the generated value is unused

Large JSON payloads can be emitted as `JSON.parse(...)`; Vite added a pure annotation to generated JSON parsing so unused JSON imports can be tree-shaken.

```javascript
// Good — generated by the client-side build transform
export default /*#__PURE__*/ JSON.parse(
  '{"labels":{"empty":"No results found","retry":"Try again"}}',
);
```

When the default export is unused, verify in the production bundle that the parse and its source string are removed.

## Anti-patterns

### Marking required registration as pure

```javascript
// Bad — blocks/consent/consent.js
const consentIntegration = /*#__PURE__*/ registerConsentIntegration({
  onConsentChanged(status) {
    window.dispatchEvent(new CustomEvent('consent-ready', { detail: status }));
  },
});

export default function decorate(block) {
  block.dataset.consentIntegration = consentIntegration.name;
}
```

**Why this is bad:** `registerConsentIntegration()` can create observable global behavior, so allowing tree-shaking to discard it can break required consent events or dependent runtime code.

### Using ESM exports in a standard CS/AMS clientlib

```javascript
// Bad — clientlibs/site-search/js/search-formatters.js
(function (window) {
  window.acme = window.acme || {};
  window.acme.siteSearch = window.acme.siteSearch || {};

  // This value is delivered as part of a standard clientlib, not an ESM module.
  // A purity annotation does not make the clientlib build tree-shake it.
  window.acme.siteSearch.searchLabels = /*#__PURE__*/ new Map([
    ['empty', 'No results found'],
  ]);
}(window));
```

**Why this is bad:** Do not assume that adding ESM exports to a clientlib enables tree-shaking. Verify the configured clientlib delivery and module-loading path before using ESM syntax.

### Assuming every constructor is safe to discard

```javascript
// Bad — clientlibs/site-base/js/component-registry.js
(function (window) {
  const componentRegistry = /*#__PURE__*/ new ComponentRegistry(window.acmeRuntime);

  window.acme = window.acme || {};
  window.acme.getComponent = function getComponent(name) {
    return componentRegistry.get(name);
  };
}(window));
```

**Why this is bad:** A constructor that reads or mutates shared runtime state may not be pure. Incorrectly annotating it can produce a bundle in which a retained export depends on initialization that was removed.

### Including a feature clientlib on every page

```html
<!-- Bad — base-page.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.js @ categories='acme.site-base,acme.site-search'}"></sly>
```

**Why this is bad:** Including the search category from the base page can make pages that do not use search receive the search code.

## Flavor-specific notes

### EDS

Trace both static imports and `import()` paths from each `decorate(block)` entry point before annotating an initializer; an apparently unused utility can still be required by a lazily loaded block enhancement.

Do not annotate expressions that define custom elements, add global listeners, modify `window`, or initialize shared runtime state unless their absence of observable side effects has been verified.

### CS

Trace the clientlib category, its `dependencies`, and every template that includes it before splitting or moving JavaScript. Inspect the publish clientlib artifact and validate the affected pages rather than relying only on source review.

Use template-controlled clientlib inclusion to scope a feature category to the templates that need it. Clientlib splitting does not replace verification of side effects in code that remains loaded.

### Headless

Apply this only in the browser-client entry and its browser chunks, not in server-side AEM consumers or API integration code. Verify tree-shaking against the deployed client build and test retained runtime paths in that build.