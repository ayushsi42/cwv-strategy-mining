---
issue_type: network-payload--move-reusable-logic-into-a-shared-package
parent_strategy: network-payload
risk_tier: low
cwv_metrics: [bundle_size_delta_pct]
source_prs: [duckduckgo/autoconsent#1044, yeojz/otplib#768, elastic/kibana#230442, sunya9/mivi#294]
required_validation:
  - shared_logic_extracted_into_reusable_module
  - call_sites_import_shared_exports_instead_of_constructing_duplicates
  - bundle_size_delta_pct_measured_before_and_after
forbidden_techniques: []
# Move reusable logic into a shared package

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metric:** bundle_size_delta_pct

## What this addresses

This strategy reduces shipped JavaScript by moving repeated logic into a shared module or package, then importing that shared implementation from multiple call sites.

### Evidence-backed mechanisms
- consolidating repeated helper logic into a shared module so consumers reuse one implementation instead of duplicating it
- replacing per-call plugin construction with shared singleton exports where the dependency is stateless
- switching from multiple CommonJS utility packages to a shared ES module utility package
- moving URL schema and utility code into a shared package consumed by multiple areas of the application
- extracting heuristic detection and popup-action logic into shared files that are imported by the runtime code

### What the evidence does not support
- a guaranteed runtime latency win
- a universal rule that every constructor should be replaced by a singleton export
- a universal rule that every utility package should be consolidated
- any CMS-, AEM-, or delivery-flavor-specific guidance

## When to apply / when to skip

### Apply when
- the same helper, schema, plugin, or detection logic is duplicated across multiple files or packages
- the shared implementation can be imported directly by consumers without changing behavior
- the extraction enables reuse or tree-shaking, or replaces repeated instantiation with a shared export
- you can measure `bundle_size_delta_pct` before and after the change

### Skip when
- the logic is already centralized and there is no duplication to remove
- the shared abstraction would add indirection without reducing shipped code
- the code must remain manually instantiated for dependency injection or custom configuration, and a shared singleton would change behavior
- the change is only a refactor with no measurable bundle-size impact

## Required validation

### `shared_logic_extracted_into_reusable_module`
**What this validates:** duplicated logic was moved into a shared module or package, and consumers now import from that shared location.

**Evidence-derived examples**
- `duckduckgo/autoconsent#1044`: heuristic detection and popup-action logic were split into shared files such as `lib/heuristics.ts` and `lib/heuristic-patterns.ts`, with consumers importing shared helpers like `getActionablePopups`, `isTopFrame`, and `isElementVisible`
- `elastic/kibana#230442`: `@kbn/data-quality` was added as a private package and re-exported shared URL schema and utility code
- `sunya9/mivi#294`: `lodash.defaultsdeep` and `lodash.merge` were replaced by `lodash-es`, consolidating utility imports onto a shared ES module package

### `call_sites_import_shared_exports_instead_of_constructing_duplicates`
**What this validates:** call sites use the shared export directly rather than creating a new instance or duplicating the helper inline.

**Evidence-derived examples**
- `yeojz/otplib#768`: examples changed from `new NodeCryptoPlugin()` / `new ScureBase32Plugin()` / `new NobleCryptoPlugin()` to shared exports like `crypto` and `base32`
- `sunya9/mivi#294`: imports changed from separate CommonJS-style utility packages to named imports from `lodash-es`
- `duckduckgo/autoconsent#1044`: popup and DOM-action code now call shared helpers and shared `clickElement` behavior instead of duplicating the same logic in multiple methods

### `bundle_size_delta_pct_measured_before_and_after`
**What this validates:** the affected bundle or delivery artifact was measured before and after the change using `bundle_size_delta_pct`.

**Evidence-derived measurements**
- `yeojz/otplib#768`: `bundle_size_delta_pct` delta `-26.21`
- `sunya9/mivi#294`: `bundle_size_delta_pct` delta `-1.04`

If no before/after measurement is available, this validation is not satisfied.

## Recommended approaches

### 1) Extract shared logic into a package or module
Move repeated helpers, schemas, or detection logic into a shared file. Re-export the shared API from a stable package entrypoint. Update consumers to import the shared API.

### 2) Prefer shared singleton exports when the dependency is intentionally stateless
Use a shared export instead of constructing a new plugin or helper at each call site. Keep manual instantiation only where the evidence shows it is needed for custom configuration or dependency injection.

### 3) Consolidate utility imports onto a tree-shakeable ES module
Replace multiple utility packages with one shared ES module package when the same functionality is already available there. Update type packages and lockfiles consistently.

## Good examples

### Shared singleton exports at call sites
```ts
import { generate, verify, crypto, base32 } from "otplib";

const token = await generate({
  secret,
  crypto,
});

const result = await verify({
  token,
  secret,
  base32,
});
```

### Consolidated utility imports
```ts
import { defaultsDeep, merge } from "lodash-es";

const merged = defaultsDeep({}, baseConfig, overrideConfig);
const finalConfig = merge({}, merged, runtimeConfig);
```

### Shared package entrypoint
```ts
export * from './url_schema';
export * from './utils/deep_compact_object';
```

### Shared detection helper
```ts
import { getActionablePopups } from './heuristics';

const popups = getActionablePopups();
if (popups.length > 0) {
  // act on the shared detection result
}
```

## Bad examples

### Per-call plugin construction
```ts
import { NodeCryptoPlugin } from "@otplib/plugin-crypto-node";

const crypto = new NodeCryptoPlugin();
```

**Why this is bad:** The supplied otplib evidence shows the bundle-size-oriented improvement came from using shared singleton exports instead of constructing new plugin instances at each call site.

### Separate CommonJS utility packages
```ts
import defaultsDeep from "lodash.defaultsdeep";
import merge from "lodash.merge";
```

**Why this is bad:** The supplied mivi evidence shows the consolidation path is to use the shared `lodash-es` package instead of keeping separate utility packages.

## How to verify

Use the same bundle-size metric before and after the extraction.

1. Measure the affected bundle or delivery artifact before the change.
2. Apply the shared-package extraction or shared-export consolidation.
3. Measure the same artifact again.
4. Compare `bundle_size_delta_pct`.

### Verification criteria
- The before and after measurements must target the same artifact.
- The import shape must change only where the shared abstraction is intended to replace duplication.
- The change should preserve behavior for existing consumers.
- The result should be reported as a measured delta, not inferred from code structure alone.

## Evidence and confidence

### Observed facts
- `duckduckgo/autoconsent#1044` extracted heuristic detection and popup-action logic into shared modules and added shared DOM-action helpers.
- `yeojz/otplib#768` replaced repeated plugin construction with shared singleton exports and documented that manual instantiation remains available when needed.
- `elastic/kibana#230442` introduced a shared private package for URL schemas and utilities.
- `sunya9/mivi#294` consolidated utility imports from separate packages onto `lodash-es`.
- The supplied measured bundle-size deltas for this strategy were negative in the improvement examples: `-26.21` and `-1.04`.

### Inference
- The common mechanism is reduced shipped JavaScript through reuse, consolidation, or tree-shakeable shared exports.
- The strategy is low risk because it is primarily a packaging and import-shape change, but only when behavior is preserved and the shared abstraction does not introduce extra runtime work.

## Risks and limitations

- Shared abstractions can hide behavior differences if the extracted code is not truly reusable.
- Replacing constructors with singleton exports is only safe when the dependency does not require per-instance state.
- A shared package can increase coupling if it becomes a dumping ground for unrelated helpers.
- Bundle-size gains are not guaranteed; the evidence includes one regression in directional consistency, so verify the actual build artifact rather than assuming improvement.
- The evidence supports bundle-size reduction, not a universal runtime performance improvement.