---
issue_type: javascript-delivery--lazy-load-optional-feature-code-after-first-paint
parent_strategy: javascript-delivery
risk_tier: low
cwv_metrics: [FCP, bundle size, main-thread parse]
source_prs:
  - clerk/javascript#7843
  - iangran/style_hacks#24
  - iangran/style_hacks#9
  - n8n-io/n8n#30834
  - webspatial/webspatial-sdk#1233
required_validation:
  - optional_feature_is_not_imported_at_module_top_level
  - runtime_path_or_call_site_gates_loading
  - lazy_loader_caches_loaded_module_or_entrypoint
forbidden_techniques: []
---
# Lazy-load optional feature code after first paint

> **Risk tier:** low · **Parent strategy:** javascript-delivery · **CWV metric:** FCP, bundle size, main-thread parse

## What this addresses

This strategy defers optional feature code until the runtime path that needs it is actually reached.

The supplied evidence supports two implementation shapes:

1. **Cached lazy loader at the call site** for a shared optional dependency
2. **Explicit eager/lazy entrypoint split** when different consumer profiles need different boot behavior

The intended effect is to reduce initial JavaScript work by keeping optional code out of the first-load path. That can lower bundle size and main-thread parse/evaluation pressure, which may help first paint when the deferred code was previously on the critical path.

## When to apply / when to skip

**Apply when:**
- the feature is optional or infrequently used
- the feature is only needed after the initial screen is already usable
- the code path is gated by a runtime condition, user action, route, or capability check
- the dependency is heavy enough that loading it at boot is undesirable
- the same module is currently imported at module top level but only some call sites need it

**Skip when:**
- the code is required for initial render or first interactive use
- the dependency is already part of the unavoidable boot path
- the feature cannot be safely deferred because it is needed for initialization or core shell rendering
- there is no clear runtime gate and the only change would be speculative code splitting

## Required validation

### `optional_feature_is_not_imported_at_module_top_level`
Confirm the optional dependency is not imported directly at module scope in the boot path.

What to check:
- a top-level runtime import is removed from the main module, or
- the main entry no longer re-exports the heavy runtime implementation directly, and
- the feature is accessed through a loader function, lazy wrapper, or explicit subpath entry

Evidence:
- `n8n-io/n8n#30834` removed direct `import { generateText, streamText, Output } from 'ai'` and replaced it with `loadAi()`
- `webspatial/webspatial-sdk#1233` moved polyfill installation to a dedicated subpath and made the default React SDK entry lazy

### `runtime_path_or_call_site_gates_loading`
Confirm the optional module is loaded only when the relevant runtime path is reached.

What to check:
- a call-site wrapper such as `loadAi().generateText(...)`
- a runtime branch that selects a lazy entry or explicit subpath
- a guard that keeps optional code out of the initial path until a condition is met

Evidence:
- `n8n-io/n8n#30834` uses `loadAi()` at the exact call sites that need `generateText`, `streamText`, `embed`, `embedMany`, `tool`, and `jsonSchema`
- `webspatial/webspatial-sdk#1233` directs web-first or SSR-capable apps to the default lazy entry and spatial-only client apps to `@webspatial/react-sdk/eager`

### `lazy_loader_caches_loaded_module_or_entrypoint`
Confirm the loader does not re-import the dependency on every use.

What to check:
- a cached module variable inside the loader, or
- a cached lazy entry wrapper that returns the same loaded module after the first access

Evidence:
- `n8n-io/n8n#30834` stores the loaded module in `_aiMod` and returns the cached module on subsequent calls
- `webspatial/webspatial-sdk#1233` uses explicit entrypoints rather than repeated ad hoc imports, which is consistent with stable module selection

## Recommended approaches

### 1) Centralize the optional dependency behind a cached loader

This is the clearest supported pattern when several call sites need the same optional package.

```ts
import type * as AiSdk from 'ai';

let _aiMod: typeof AiSdk | undefined;

export function loadAi(): typeof AiSdk {
  if (!_aiMod) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('ai') as typeof AiSdk;
    _aiMod = mod;
  }
  return _aiMod;
}
```

Use the loader at the point of use:

```ts
const { generateText } = loadAi();

const result = await generateText({
  model,
  messages,
});
```

This matches the evidence from `n8n-io/n8n#30834`, where runtime code was refactored to call `loadAi()` instead of importing `ai` at module scope.

### 2) Split eager and lazy entrypoints when the product has distinct boot profiles

If one consumer profile needs the feature immediately and another does not, explicit entrypoints are supported by the evidence.

```ts
import { bootSpatial } from '@webspatial/react-sdk';
import { bootSpatial as bootSpatialEager } from '@webspatial/react-sdk/eager';
```

The evidence from `webspatial/webspatial-sdk#1233` supports:
- a lazy default entry
- an eager entry for a narrower client-only profile
- explicit subpaths for runtime-only code and polyfills

### 3) Keep optional feature access behind the exact runtime branch that needs it

When the feature is only needed after a condition is confirmed, route access through that branch rather than importing it globally.

```ts
if (this.config.memory.queryEmbeddings && this.config.semanticRecall.embedder) {
  const { embed } = getAiSdk();
  // use embed only in the embedding path
}
```

This is consistent with `n8n-io/n8n#30834`, where embedding and generation paths load the SDK only when those paths execute.

## Good examples

### Good: cached lazy loader
```ts
import type * as AiSdk from 'ai';

let _aiMod: typeof AiSdk | undefined;

export function loadAi(): typeof AiSdk {
  if (!_aiMod) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('ai') as typeof AiSdk;
    _aiMod = mod;
  }
  return _aiMod;
}
```

Why this is good:
- the optional dependency is not imported at module top level
- the loaded module is cached after first access
- the loader can be reused across multiple call sites

### Good: call-site gating
```ts
if (this.config.memory.queryEmbeddings && this.config.semanticRecall.embedder) {
  const { embed } = getAiSdk();
}
```

Why this is good:
- the optional code is only loaded on the embedding path
- the initial boot path does not pay for the dependency unless the feature is used

### Good: explicit lazy/eager entry split
```ts
import { bootSpatial } from '@webspatial/react-sdk';
import { bootSpatial as bootSpatialEager } from '@webspatial/react-sdk/eager';
```

Why this is good:
- the default entry can stay lighter for web-first or SSR-capable apps
- the eager entry is reserved for the narrower client-only profile that needs it

## Bad examples

### Bad: top-level runtime import of an optional heavy dependency
```ts
import { generateText, streamText, embedMany } from 'ai';

export async function run() {
  return generateText({ model, messages: [] });
}
```

Why this is bad:
- it forces the optional runtime dependency into the initial module graph
- it increases boot-time JavaScript work
- it defeats the lazy-loading pattern shown in the evidence

### Bad: re-exporting runtime-heavy code from the main entry when a dedicated subpath exists
```ts
export { installPolyfills } from '@webspatial/core-sdk';
```

Why this is bad:
- the evidence shows polyfill installation was moved to a dedicated subpath
- consumers should import the explicit subpath only when they need that side effect

## How to verify

Use measurable checks that match the delivery change:

1. **Inspect the module graph**
   - confirm the optional dependency is no longer imported at top level in the boot path
   - confirm the loader or explicit subpath is the only access path

2. **Measure bundle impact**
   - compare initial-entry bundle size before and after
   - confirm the optional module is absent from the first-load chunk when it should be deferred

3. **Measure startup work**
   - compare main-thread parse/evaluation time during startup
   - confirm the deferred code is not parsed until the gated path is exercised

4. **Check runtime behavior**
   - verify the optional feature still loads and works when the gated path is exercised
   - verify the eager path still works when the feature is not needed

Do not expect a fixed improvement from this strategy alone. The effect depends on how much code was deferred and whether that code was previously on the critical path.

## Evidence and confidence

### Observed facts
- `n8n-io/n8n#30834` introduced `src/runtime/lazy-ai.ts` with a cached `require('ai')` loader and replaced direct `ai` imports with `loadAi()` at call sites.
- `webspatial/webspatial-sdk#1233` restructured runtime packaging around explicit ESM subpaths, moved polyfill installation to a dedicated subpath, and made the React SDK default entry lazy with an eager alternative.
- `iangran/style_hacks#9` shows a request-dispatch refactor in which runtime dependency access is centralized rather than eagerly imported.
- `iangran/style_hacks#24` is a static role data file and does not materially add mechanism evidence for lazy loading.

### Inference
- Deferring optional feature code until after first paint can reduce initial JavaScript work and may improve FCP when the deferred code was previously part of the boot path.
- A cached loader or explicit subpath split is safer than ad hoc repeated loading because it preserves stable module identity and avoids repeated loading logic.

### Confidence
Medium. The mechanism is directly supported by multiple source PRs, but the supplied evidence does not include numeric measured deltas, so the playbook should remain conditional rather than promising a specific CWV gain.

## Risks and limitations

- If the deferred code is actually needed for first render, lazy loading can delay visible functionality or create a loading gap.
- If the loader is placed too late, the user may hit a feature boundary before the module is ready.
- If the optional module has side effects that other code depends on, moving it behind a loader or subpath can require additional initialization changes.
- Explicit eager/lazy entrypoint splits require consumers to choose the correct entry; mixing them in one bundle can reintroduce the boot cost or create duplicate behavior.
- This strategy is about delivery shape, not algorithmic optimization; it will not fix expensive work that remains in the critical path.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (5 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **5 observations across 4 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: javascript-delivery--lazy-load-optional-feature-code-after-first-paint`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
