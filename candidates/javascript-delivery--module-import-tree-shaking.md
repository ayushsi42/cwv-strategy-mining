---
issue_type: javascript-delivery--module-import-tree-shaking
parent_strategy: javascript-delivery
risk_tier: low
cwv_metrics: [bundle_size_delta_pct]
source_prs: [Tresjs/tres#1372, MetaMask/metamask-design-system#975, CodinGame/monaco-vscode-api#780, datahub-project/datahub#16338]
required_validation:
  - import_surface_reduced
  - direct_symbol_imports_used
  - no_broad_package_import_for_tree_shakeable_symbols
forbidden_techniques: []
---
# Module import tree-shaking

> **Risk tier:** low · **Parent strategy:** javascript-delivery · **CWV metric:** bundle_size_delta_pct

## What this addresses

This strategy reduces delivered JavaScript by narrowing the import surface to only the exports actually used by the consuming code.

The evidence supports three related mechanisms:

1. **Import only the referenced symbol(s)** instead of a broader module surface.
2. **Prefer direct per-symbol entry points** when a library exposes tree-shakeable subpaths.
3. **Replace broad re-export patterns with smaller constant-object exports** when the consumer only needs a finite value map.

The supplied statistical summary reports:

- 8 observations across 8 repositories
- 100.0% directional consistency
- absolute measured-delta summary: `p25=19.92`, `median=19.92`, `p75=19.92`

These figures support a consistent bundle-size reduction signal, but they do not guarantee the same delta in every codebase.

## When to apply / when to skip

### Apply when
- A bundle includes a dependency surface larger than the code actually uses.
- A library exposes per-symbol or per-entry exports and the current code imports a broader package namespace.
- A module re-exports a large API, but the consumer only needs a small set of values.
- You can replace runtime enum-like usage with a shared const object or direct named export without changing behavior.

### Skip when
- The import is already a minimal direct symbol import and there is no broader surface to reduce.
- The module’s side effects are required for correctness and there is no safe narrower import path.
- The code depends on runtime behavior tied to a specific constructor or module initialization and no equivalent smaller export exists.
- You cannot confirm that the narrower import preserves the same semantics across the supported revision range.

## Required validation

### `import_surface_reduced`

**Goal:** confirm that the change narrows the import surface.

**Pass when all are true:**
- A broad package import is replaced by a direct symbol import, a per-entry import, or a smaller shared export.
- The consuming code references the imported symbol directly rather than through a namespace object or large wrapper module.
- The resulting code path still resolves to the same behavior in the target runtime.

**Evidence-derived examples:**
- `datahub-project/datahub#16338` replaces package-level Phosphor icon imports with direct CSR symbol imports such as `@phosphor-icons/react/dist/csr/Copy`.
- `MetaMask/metamask-design-system#975` moves severity values to a shared `BannerAlertSeverity` export and consumes that smaller surface from the component package.
- `Tresjs/tres#1372` introduces a local timer abstraction so consumers no longer import `Timer` directly from `three` in each usage site.

### `direct_symbol_imports_used`

**Goal:** confirm that the consumer imports the specific symbol it uses.

**Pass when all are true:**
- The import statement names the exact export or entry point needed.
- The code does not import a namespace solely to reach one member.
- The rendered or bundled code path uses the imported symbol directly.

**Evidence-derived examples:**
- `datahub-project/datahub#16338` changes to imports such as `import { Copy } from '@phosphor-icons/react/dist/csr/Copy'`.
- `MetaMask/metamask-design-system#975` exports `BannerAlertSeverity` from the component package and uses it directly in docs and component code.
- `CodinGame/monaco-vscode-api#780` expands the set of constructors treated as side-effectful, which is a reminder that direct symbol usage must still preserve constructor semantics when tree-shaking is involved.

### `no_broad_package_import_for_tree_shakeable_symbols`

**Goal:** confirm that a broader package import is not retained when a smaller tree-shakeable path exists.

**Pass when all are true:**
- The old broad import is removed.
- The replacement path is a narrower entry point or a smaller shared export.
- There is no evidence that the broader import is still required for side effects.

**Evidence-derived examples:**
- `datahub-project/datahub#16338` adds a lint restriction against importing `@phosphor-icons/react` at package level for icons that have individual CSR paths.
- `MetaMask/metamask-design-system#975` documents migration from extension-local enum imports to the shared `BannerAlertSeverity` export.
- `Tresjs/tres#1372` centralizes timer creation behind `createTimer()` so consumers do not need to import the broader `Timer` class directly.

## Recommended approaches

Use the smallest export surface that preserves behavior.

### Good: direct per-symbol import

```ts
import { Copy } from '@phosphor-icons/react/dist/csr/Copy';
import { Icon } from '@components';

export const CopyButton = ({ text }: Props) => (
  <Button variant="text" color="gray" size="sm" onClick={() => copyToClipboard(text)}>
    <Icon icon={Copy} size="xs" />
  </Button>
);
```

**Why this is good:** it imports the icon from a direct per-symbol CSR path rather than from the package root.

### Good: shared const-object export

```ts
export const BannerAlertSeverity = {
  Info: 'info',
  Success: 'success',
  Warning: 'warning',
  Danger: 'danger',
} as const;
```

**Why this is good:** it matches the evidence pattern of a small, explicit value surface that consumers can import directly.

### Good: local wrapper around a broader constructor

```ts
export function createTimer(): TresTimer {
  if (revision >= TIMER_MIN_REVISION) {
    const timer = new THREE.Timer();

    return {
      getDelta: () => timer.getDelta(),
      getElapsed: () => timer.getElapsed(),
      update: () => timer.update(),
      start: () => {
        if (typeof document !== 'undefined') {
          timer.connect(document);
        }
      },
      stop: () => timer.disconnect(),
    };
  }

  const clock = new THREE.Clock();

  return {
    getDelta: () => clock.getDelta(),
    getElapsed: () => clock.elapsedTime,
    update: () => {},
    start: () => clock.start(),
    stop: () => clock.stop(),
  };
}
```

**Why this is good:** it preserves behavior while allowing consumers to avoid direct broad imports.

## Anti-patterns

### Bad: namespace import for a single symbol

```ts
import * as Icons from '@phosphor-icons/react';

export const CopyButton = () => <Icon icon={Icons.Copy} />;
```

**Why this is bad:** the evidence supports narrowing imports to direct symbol paths when the goal is bundle reduction. A namespace import keeps the broader package surface in play and works against tree-shaking.

### Bad: keeping a local enum source when a shared export exists

```ts
import { BannerAlertSeverity } from './banner-alert.types';
```

**Why this is bad:** the MetaMask migration evidence moves severity values to the shared package export, not a local enum source. Keeping a local source defeats the smaller shared export surface and the documented migration path.

If your codebase already uses the smallest supported import surface and there is no broader package import to replace, the evidence is insufficient to justify a stronger anti-pattern claim.

## How to verify

Use the same measurement family already present in the evidence: `bundle_size_delta_pct`.

### Verification steps
1. Measure the baseline bundle size before the import change.
2. Apply the narrower import or smaller export surface.
3. Re-measure the same bundle artifact or delivery bundle.
4. Compare the before/after `bundle_size_delta_pct`.

### Pass criteria
- The post-change bundle is smaller than the baseline.
- The import path is narrower and behavior remains unchanged.
- The change does not introduce a required side effect regression.

### Interpretation
- A negative delta indicates a smaller bundle.
- A flat or positive delta means the change did not reduce delivered JavaScript and should be reviewed for import-path correctness or dead-code retention.

Do not assume a fixed improvement. The supplied evidence shows directional consistency, but the exact delta depends on the dependency graph and the specific symbols imported.

## Evidence and confidence

### Observed facts
- `Tresjs/tres#1372` introduces `createTimer()` and routes consumers through that abstraction instead of importing `Timer` directly in each consumer.
- `MetaMask/metamask-design-system#975` migrates severity values to a shared `BannerAlertSeverity` const object and updates docs/examples to import it from the design-system package.
- `CodinGame/monaco-vscode-api#780` expands the set of constructors treated as side-effectful, showing that tree-shaking decisions must preserve constructor semantics.
- `datahub-project/datahub#16338` adds a lint restriction against broad `@phosphor-icons/react` imports and replaces them with direct CSR icon entry-point imports.
- The supplied statistical summary reports 8 observations across 8 repositories, 100.0% directional consistency, and a measured-delta summary with `p25=19.92`, `median=19.92`, `p75=19.92` for `bundle_size_delta_pct`.

### Inference
- Narrowing imports is a low-risk delivery optimization when the replacement path is behaviorally equivalent and the dependency exposes tree-shakeable entry points.
- The same mechanism generalizes across icon imports, shared const-object exports, and local wrappers around broader constructors, but only where the evidence shows the narrower surface preserves behavior.

Confidence is medium because the evidence is consistent and cross-repository, but the raw measurements are sparse and some source PRs do not include explicit before/after numbers in the supplied material.

## Risks and limitations

- Tree-shaking benefits depend on the module graph and bundler behavior; a narrower import does not guarantee a smaller bundle in every case.
- Some constructors or modules have required side effects, and the evidence shows that these must be preserved rather than aggressively removed.
- Direct per-symbol imports can increase maintenance burden if the upstream package reorganizes entry points.
- Shared const-object exports are only appropriate when the value set is finite and stable enough to model explicitly.
- This strategy should not be used to justify speculative refactors without a measurable bundle-size check.