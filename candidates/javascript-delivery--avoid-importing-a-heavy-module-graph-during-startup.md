---
issue_type: javascript-delivery--avoid-importing-a-heavy-module-graph-during-startup
parent_strategy: javascript-delivery
risk_tier: medium
cwv_metrics:
  - Lighthouse JavaScript execution
  - Lighthouse main-thread work
  - Lighthouse JS execution / startup stability
  - startup time
source_prs:
  - rhencke/tracy#276
  - trezor/trezor-suite#22446
  - web-infra-dev/rspack#12733
required_validation:
  - built_dependency_available_before_runtime_import
  - startup_import_path_does_not_traverse_broken_graph
forbidden_techniques: []
---

# Avoid importing a heavy module graph during startup

> **Risk tier:** medium · **Parent strategy:** javascript-delivery · **CWV metrics:** Lighthouse JavaScript execution, Lighthouse main-thread work, Lighthouse JS execution / startup stability, startup time

## What this addresses

This strategy applies when startup work is caused by traversing a module graph too early, before its dependent build output or runtime prerequisites are ready.

The evidence supports two distinct but related patterns:

1. **Defer a runtime import until a readiness signal is available.**  
   In `rhencke/tracy#276`, `bootstrap.mjs` no longer imports `./host/wasm-modules.mjs` directly during bootstrap. Instead, it waits on `coreReadyPromise` and then imports the wasm module graph through `importWasmModules()`.

2. **Make sure a dependent build artifact exists before any runtime path can import it.**  
   In `trezor/trezor-suite#22446`, the e2e setup runs `yarn message-system-sign-config` before Playwright runtime can indirectly import the built config, with an explicit note that the runtime import would crash if `message-system` is not built.

The shared mechanism is narrow: **do not let startup traverse a module graph whose prerequisite build output is missing or whose initialization must wait for a readiness boundary.**

## Apply / skip

### Apply

Use this strategy when all of the following are true:

- Startup imports a module graph that depends on generated build output or another prerequisite artifact.
- That prerequisite may not exist yet when the runtime path is reached.
- The module is not needed until after a clear readiness boundary.
- You can move the import behind a gate without changing the module’s required behavior.

### Skip

Do not use this strategy when any of the following are true:

- The module is required synchronously for first render or immediate boot correctness.
- The problem is code size, repeated execution, or render-tree depth rather than import timing.
- There is no evidence that the graph is broken, deferred, or build-dependent.
- The module is already loaded only on demand and there is no startup traversal to remove.

## Required validation

### `built_dependency_available_before_runtime_import`

**What this means:**  
The evidence must show that a prerequisite build step or generated artifact is established before a runtime path can import it.

**How to verify:**
- Confirm that a build/setup step runs before the runtime import path is exercised.
- Confirm that the runtime path would fail or crash without that prerequisite.
- Confirm that the change enforces build order rather than merely changing code style.

**Evidence-derived example:**
- `trezor/trezor-suite#22446` adds `yarn message-system-sign-config` before Playwright runtime can indirectly import the built config, and the code comment states that the runtime import would crash if `message-system` is not built.

### `startup_import_path_does_not_traverse_broken_graph`

**What this means:**  
The startup path must no longer directly traverse the problematic graph.

**How to verify:**
- Confirm that the direct import is replaced by a deferred wrapper or readiness-gated import.
- Confirm that the import occurs only after a readiness condition is satisfied.
- Confirm that the startup path no longer contains the direct graph import.

**Evidence-derived example:**
- `rhencke/tracy#276` introduces `coreReadyPromise` and `importWasmModules()`, and `bootstrap.mjs` now imports `./host/wasm-modules.mjs` only after `coreReadyPromise` resolves.

## Recommended approaches

### Gate the import on a readiness signal

Use a promise or event that represents the point after which the dependent graph is safe to load.

```js
const coreReadyPromise = new Promise((resolve) => {
  if (
    performance.getEntriesByName(PERFORMANCE_MARKS.coreReady).length > 0 ||
    typeof globalThis.addEventListener !== "function"
  ) {
    resolve();
  } else {
    globalThis.addEventListener(PERFORMANCE_MARKS.coreReady, resolve, { once: true });
  }
});

const importWasmModules = async () => {
  await coreReadyPromise;
  return import(`./host/${RUNTIME_URLS.WASM_MODULES_URL.replace(/^\.\//, "")}`);
};
```

This matches the evidence in `rhencke/tracy#276`: the import is deferred until the app reaches a known-ready state.

### Keep the startup path free of the direct graph import

```js
async function instantiateWasmModuleForThread(id, thread, imports, options = {}) {
  if (id !== "app" || thread !== "main") {
    const { instantiateWasmModuleForThread: instantiateWasmGraph } = await importWasmModules();
    return instantiateWasmGraph(id, thread, imports, options);
  }

  const url = `${(options.baseUrl ?? "wasm/").replace(/\/?$/, "/")}app.wasm`;
  // ...
}
```

This preserves the startup boundary while still allowing the module graph to load when needed.

### Ensure build prerequisites exist before indirect runtime imports

If a runtime tool or test harness can indirectly import a generated config or module graph, run the prerequisite build step before that runtime begins.

```yaml
# Playwright runtime may indirectly import the built config, and that would crash if message-system is not built
yarn message-system-sign-config
```

This is the exact evidence pattern from `trezor/trezor-suite#22446`: the fix is to make the prerequisite available first, not to recover after the crash.

## Good / bad examples

### Good: readiness-gated deferred import

```js
const { instantiateWasmModuleForThread: instantiateWasmGraph } =
  await importWasmModules();
```

**Why this is good:** The import is not executed during bootstrap. It happens only after the readiness gate resolves, which matches the evidence-backed pattern in `rhencke/tracy#276`.

### Bad: direct startup import of the graph

```js
const { instantiateWasmModuleForThread: instantiateWasmGraph } =
  await import("./host/wasm-modules.mjs");
```

**Why this is bad:** This traverses the graph immediately. In the evidence, the direct startup import is replaced because the graph should not be loaded until readiness is established.

### Good: build prerequisite before runtime import

```yaml
yarn message-system-sign-config
```

**Why this is good:** The prerequisite build step runs before Playwright runtime can indirectly import the built config, preventing the crash described in the evidence.

## Verification

Use the same measurement family associated with the issue:

- Lighthouse JavaScript execution
- Lighthouse main-thread work
- Lighthouse JS execution / startup stability
- startup time

Verify with measurable checks:

1. The startup path no longer imports the heavy or generated module graph directly.
2. The readiness gate is reached before the deferred import executes.
3. The prerequisite build step runs before any runtime path that can indirectly import the generated module.
4. Startup no longer fails early because of a missing built dependency or broken graph.

Do not assume a fixed numeric improvement. The supplied evidence supports a directional expectation only: less startup work and better startup stability when the graph is not traversed too early.

## Evidence and confidence

### Observed facts

- `trezor/trezor-suite#22446` adds a build/setup step before Playwright runtime can indirectly import a built config, with an explicit crash-prevention comment.
- `rhencke/tracy#276` introduces `WASM_MODULES_URL`, `coreReadyPromise`, and `importWasmModules()`, and changes bootstrap to await readiness before importing the wasm module graph.
- `web-infra-dev/rspack#12733` shows a related startup-path simplification in a CLI package by moving to direct ESM imports and removing an internal helper indirection.

### Inference

- The common strategy is to prevent startup from traversing a module graph before its prerequisites are available or before the app has reached a readiness boundary.
- This should reduce startup work and startup instability, but the supplied evidence does not include numeric deltas for this child strategy.

### Confidence

- **Medium.** The mechanism is consistent across three repositories, but the measured deltas are unavailable in the supplied evidence.

## Risks and limitations

- Deferring a module graph can shift work later rather than remove it; if the module is needed immediately, this can hurt perceived responsiveness.
- A readiness gate must be reliable; if it never fires, the deferred import will stall.
- Build-order fixes only help when the failure is caused by missing generated output or an unbuilt dependency.
- The evidence supports conditional deferral and prerequisite enforcement, not blanket lazy loading of all startup modules.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: javascript-delivery--avoid-importing-a-heavy-module-graph-during-startup`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
