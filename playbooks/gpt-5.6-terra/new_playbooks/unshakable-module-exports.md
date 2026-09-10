---
issue_type: unshakable-module-exports
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- package_publish_surface_owned
- consumer_bundler_esm_support_confirmed
- package_side_effects_audited
- conditional_exports_resolution_tested
- public_deep_imports_inventory_built
- production_bundle_size_baseline_captured
forbidden_techniques:
- pattern: '"type"\s*:\s*"commonjs"'
  reason: Avoid converting a package to CommonJS-only output when browser consumers
    need ESM tree-shaking
- pattern: '"\."\s*:\s*"\.?/[^"]*\.cjs"'
  reason: Avoid exposing a CommonJS file as the only root package export when an ESM
    export can be provided for consumers
flavor_overrides:
  eds:
    extra_validation:
    - block_import_usage_traced
  cs:
    extra_validation:
    - clientlib_build_pipeline_esm_support_confirmed
    - clientlib_category_consumers_traced
  ams:
    extra_validation:
    - clientlib_build_pipeline_esm_support_confirmed
    - legacy_browser_support_confirmed
  headless:
    extra_validation:
    - frontend_runtime_and_ssr_import_paths_tested
source_prs:
- chrisllontop/qrex#26
- projectwallace/format-css#119
- maccuaa/intellitrust-js-sdk#766
- foxglove/three-text#449
- aws-amplify/amplify-ui#195
- Sage/carbon#4623
- prettier/prettier#12740
- fremtind/jokul#2919
- nsbno/spor#396
- airman5573/mockpress#8
- LyraSearch/lyra#216
- jellyfin/jellyfin-sdk-typescript#420
- open-formulieren/formio-renderer#26
- quiknode-labs/qn-oss#76
- readmeio/oas#793
- readmeio/httpsnippet#194
- digdir/designsystem#882
- algorand/js-algorand-sdk#836
- Yomguithereal/mnemonist#214
- chanzuckerberg/edu-design-system#1856
---
# Unshakable module exports

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless

## What this addresses

CommonJS-only packages and incorrect side-effect declarations can prevent consumer bundlers from removing unused code. Publishing traceable ESM exports can allow consumer builds to remove unused modules.

## When to apply / when to skip
**Apply when:**
- Bundle analysis identifies a dependency or internal shared package whose unused exports remain in a browser bundle.
- The package is owned by the project, or its source and publishing configuration are available for a coordinated fix.
- The consumer build can resolve package `exports` conditions and consume ESM output.
- Side effects, including CSS imports, have been audited.

**Do not apply yet when:**
- The package is consumed by tooling that cannot consume the proposed ESM or conditional-export surface.
- Existing consumers depend on deep imports and their migration impact is not known.
- The candidate module intentionally performs required import-time work that cannot safely be separated from pure exports.

## Recommended approaches

### Good: publish explicit ESM and CommonJS conditions

Publish an ESM entry point while retaining a separate CommonJS condition where existing Node-based consumers require it.

```json
{
  "name": "@acme/aem-utils",
  "sideEffects": false,
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.js",
      "types": "./dist/types/index.d.ts"
    },
    "./package.json": "./package.json"
  },
  "main": "./dist/index.js",
  "types": "./dist/types/index.d.ts"
}
```

```javascript
// Good: packages/aem-utils/src/index.js
export { formatPrice } from './format-price.js';
export { createSearchQuery } from './search-query.js';
```

Explicit `import` and `require` conditions provide ESM and CommonJS entry points. ESM exports can give bundlers a tree-shakable module surface.

### Keep import-time side effects in a dedicated entry point

Mark a package as side-effect-free only after required side effects, such as CSS imports, have been accounted for.

```json
{
  "name": "@acme/aem-utils",
  "sideEffects": [
    "./dist/styles.css"
  ],
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.js"
    },
    "./styles.css": "./dist/styles.css"
  }
}
```

```javascript
// packages/aem-utils/src/styles.js
import './styles.css';
```

```javascript
// packages/aem-utils/src/index.js
export { formatPrice } from './format-price.js';
export { createSearchQuery } from './search-query.js';
```

A scoped `sideEffects` declaration can preserve files that must remain in the build while allowing unused pure modules to be removed. Do not use `sideEffects: false` until CSS imports have been accounted for.

### EDS: import only the named block capability needed

Use named ESM imports rather than loading a package namespace.

```javascript
// Good: blocks/search/search.js
export default async function decorate(block) {
  const { createSearchQuery } = await import('./search-query.js');
  const input = block.querySelector('input[type="search"]');

  input?.addEventListener('input', () => {
    const query = createSearchQuery(input.value);
    block.dataset.query = query;
  });
}
```

Named ESM imports provide a statically analyzable module surface for consumer bundlers.

## Anti-patterns

### CommonJS-only root export

**Bad:**

```json
{
  "name": "@acme/aem-utils",
  "type": "commonjs",
  "exports": {
    ".": "./dist/index.cjs"
  },
  "main": "./dist/index.cjs"
}
```

**Why this is bad:** A CommonJS-only root entry does not provide an ESM entry point for consumers that rely on ESM tree-shaking.

### Blanket `sideEffects: false` while importing CSS

**Bad:**

```json
{
  "name": "@acme/aem-utils",
  "sideEffects": false
}
```

```javascript
import './styles.css';
```

**Why this is bad:** Declaring all files side-effect-free can cause a consumer build to remove CSS imports that must be retained.