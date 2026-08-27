---
issue_type: javascript-delivery--import-a-single-module-entry-instead-of-a-package-barrel
parent_strategy: javascript-delivery
risk_tier: low
cwv_metrics:
  - bundle size
  - JS delivery
  - Lighthouse JavaScript payload
  - Lighthouse JavaScript execution
source_prs:
  - palantir/osdk-ts#2104
  - powerhouse-inc/powerhouse#2079
  - superplanehq/superplane#5264
required_validation:
  - package_barrel_import_present
  - direct_module_entry_available
  - no_initial_bundle_dependency_on_barrel_for_referenced_symbols
forbidden_techniques: []
---

# Import a single module entry instead of a package barrel

> **Risk tier:** low · **Parent strategy:** javascript-delivery · **CWV metric:** bundle size / JS delivery / Lighthouse JavaScript payload / Lighthouse JavaScript execution

## What this addresses

This strategy reduces JavaScript delivery cost by replacing broad package-root imports with narrower module entries. The evidence supports two related mechanisms:

1. importing only the needed symbols from direct subpath modules instead of a package barrel
2. exposing stable subpath exports so consumers can reach those modules without going through the package root

In the supplied evidence, the consumer code moved from `@powerhousedao/connect` to direct entries such as `@powerhousedao/connect/components/app`, `@powerhousedao/connect/hooks`, `@powerhousedao/connect/services`, `@powerhousedao/connect/store`, `@powerhousedao/connect/context`, and `@powerhousedao/connect/utils`. The package metadata was updated to publish those subpaths explicitly.

The expected effect is a smaller initial JavaScript graph because the bundler no longer needs to traverse a broad re-export surface to resolve a few used symbols.

## Apply / skip gates

### Apply when

- the current code imports multiple symbols from a package root or barrel
- the needed symbols already exist in narrower module files or exported subpaths
- the package can expose stable subpath entries without changing runtime behavior
- the change can be made by redirecting imports, not by inventing new APIs
- the package structure already separates concerns into modules such as components, hooks, services, store, context, utils, or similar feature entries

### Skip when

- the package root is the only supported public entrypoint for the symbol
- the narrower path is not exported or not available in package metadata
- the package root performs required initialization that the narrower path does not
- the change would require a new public API shape not supported by the repository evidence
- the import is already a narrow module entry and there is no barrel dependency to remove

## Required validation

### `package_barrel_import_present`

**What to check:** confirm that the pre-change code path used a broad package entrypoint for symbols that were later split into narrower imports.

**Evidence-derived meaning:** in `powerhouse-inc/powerhouse#2079`, files under `apps/connect/src/components` originally imported multiple symbols from `@powerhousedao/connect`. The patch replaced those imports with direct module paths.

**Pass condition:** at least one consumer file imports from a package root or barrel, and the same file is later changed to import the same functionality from narrower module entries.

---

### `direct_module_entry_available`

**What to check:** confirm that the package exposes a concrete subpath entry for the symbol being imported.

**Evidence-derived meaning:** `apps/connect/package.json` and `apps/connect/package.copy.json` added explicit exports for:

- `./components`
- `./components/*`
- `./hooks`
- `./hooks/*`
- `./services`
- `./services/*`
- `./store`
- `./store/*`
- `./context`
- `./context/*`
- `./utils`
- `./utils/*`
- `./pages`
- `./pages/*`
- `./i18n`

**Pass condition:** the imported path resolves to a declared export or a concrete module file, not just a package root barrel.

---

### `no_initial_bundle_dependency_on_barrel_for_referenced_symbols`

**What to check:** confirm that the application entrypoint no longer depends on the barrel for the referenced symbols.

**Evidence-derived meaning:** the `powerhouse-inc/powerhouse#2079` consumer files now import the same symbols directly from subpaths, so the package root is no longer required to reach those symbols in the initial load path.

**Pass condition:** the symbols used during initial render are imported from direct module entries, and the package root is not needed to resolve them.

## Evidence-derived good examples

### Good: replace a package-root import with direct module imports

```ts
import { App } from "@powerhousedao/connect/components/app";
import { AppSkeleton } from "@powerhousedao/connect/components/app-skeleton";
import { CookieBanner } from "@powerhousedao/connect/components/cookie-banner";
import { ModalsContainer } from "@powerhousedao/connect/components/modal/modals-container";
import { useCheckLatestVersion } from "@powerhousedao/connect/hooks";
import { useSubscribeToVetraPackages } from "@powerhousedao/connect/services";
import { createReactor, useSetSentryUser } from "@powerhousedao/connect/store";
import { ProcessorManagerProvider, SentryProvider } from "@powerhousedao/connect/context";
import { DocumentEditorDebugTools, serviceWorkerManager } from "@powerhousedao/connect/utils";
```

**Why this is good:** this matches the observed change in `apps/connect/src/components/app-loader.tsx`, `app.tsx`, `cookie-banner.tsx`, `analytics.tsx`, `app-skeleton.tsx`, and `document-editor-container.tsx`, where the package-root import was replaced by narrower entries.

---

### Good: expose stable subpath exports

```json
{
  "exports": {
    ".": {
      "source": "./src/index.ts",
      "import": "./lib/src/index.js",
      "types": "./lib/src/index.d.ts"
    },
    "./components": {
      "source": "./src/components/index.ts",
      "import": "./lib/src/components/index.js",
      "types": "./lib/src/components/index.d.ts"
    },
    "./components/*": {
      "source": "./src/components/*",
      "import": "./lib/src/components/*.js",
      "types": "./lib/src/components/*.d.ts"
    }
  }
}
```

**Why this is good:** the package metadata in the evidence added explicit exports for narrower entries, making direct imports stable and public.

---

### Good: import a single feature module instead of the package root

```ts
import { useAcceptedCookies } from "@powerhousedao/connect/hooks/useAcceptedCookies";
import { openUrl } from "@powerhousedao/connect/utils/openUrl";
import { DocumentEditor } from "@powerhousedao/connect/components/editors";
```

**Why this is good:** the evidence shows direct feature-module imports replacing root imports for these symbols.

## Evidence-derived bad examples

### Bad: import many symbols from the package root

```ts
import {
  App,
  AppSkeleton,
  CookieBanner,
  ModalsContainer,
  useCheckLatestVersion,
  useSubscribeToVetraPackages,
  useSetSentryUser,
  createReactor,
} from "@powerhousedao/connect";
```

**Why this is bad:** the evidence shows this exact pattern was replaced with narrower module entries to avoid broad re-export graphs.

---

### Bad: rely on the package root when a direct entry exists

```ts
import { useAcceptedCookies } from "@powerhousedao/connect";
```

**Why this is bad:** the evidence shows a direct hook entry was available and used instead.

## Verification

Verification must be measurable and tied to the repository’s existing build or analysis tooling.

Check that:

- the build still succeeds after switching to direct module entries
- the package exports resolve for every imported subpath
- bundle analysis or Lighthouse JavaScript payload is reviewed before and after the change
- JavaScript delivery and JavaScript execution are compared using the same measurement method on both revisions

Do not assume a fixed improvement. The evidence includes directional consistency across three repositories, but no absolute delta summary was provided.

## Evidence

### Observed facts

- In `powerhouse-inc/powerhouse#2079`, consumer files moved from `@powerhousedao/connect` to direct subpath imports for components, hooks, services, store, context, utils, and i18n.
- In the same PR, `apps/connect/package.json` and `apps/connect/package.copy.json` added explicit exports for those subpaths and set `sideEffects: false`.
- In `palantir/osdk-ts#2104`, the widget API surface was narrowed by importing `ObjectTypeDefinition` from `@osdk/api` and extending the widget client-react package through a more specific dependency boundary.
- In `superplanehq/superplane#5264`, the command palette code removed unused command surfaces from the initial UI path, which is consistent with pruning what is loaded up front, but it is not a package-barrel example.

### Inference

- Direct module imports are the supported mechanism for reducing initial JavaScript delivery when a package root barrel would otherwise pull in more code than needed.
- Explicit subpath exports are the enabling package-level change that makes those direct imports stable and consumable.
- `sideEffects: false` can help tree-shaking, but only when module boundaries are already correct and the package does not rely on hidden initialization side effects.

### Confidence

Medium. The evidence is directionally consistent across three repositories, but the supplied measurements do not include absolute deltas.

## Risks and limitations

- This strategy is only safe when the narrower module path is a true public entrypoint for the needed symbol.
- If the package root performs initialization or re-exports symbols with side effects, bypassing it can change runtime behavior.
- Adding many subpath exports can improve import precision, but it also increases package surface area and maintenance burden.
- `sideEffects: false` should be used carefully; the evidence supports it only in a package that is already being consumed through explicit module entries.
- The supplied evidence does not justify claiming a guaranteed bundle-size reduction for every repository; verification must be measurement-based.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: javascript-delivery--import-a-single-module-entry-instead-of-a-package-barrel`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
