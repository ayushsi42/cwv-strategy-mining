---
issue_type: network-payload--move-optional-dependency-import-behind-a-code-path
parent_strategy: network-payload
risk_tier: low
cwv_metrics:
  - bundle size / initial load
  - bundle size / initial JS payload
  - bundle size / Lighthouse JS payload
  - bundle size increase
  - perf_flagged
source_prs:
  - apollographql/apollo-client#12836
  - aws/graph-explorer#1349
  - cowprotocol/cowswap#6338
  - romunus/normalize-charset#17
  - tomasondavis/react_hermes_parser#19
required_validation:
  - optional_dependency_is_not_imported_at_module_top_level
  - heavy_feature_is_only_loaded_inside_user_gated_code_path
  - fallback_render_path_exists_when_optional_asset_or_module_is_unavailable
forbidden_techniques: []
---

# Move optional dependency import behind a code path

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metrics:** bundle size / initial JS payload, bundle size / Lighthouse JS payload

## What this addresses

This strategy reduces initial JavaScript payload by keeping an optional, feature-specific dependency out of the module’s top-level execution path.

The evidence supports three concrete patterns:

- A dialog-only Monaco editor is isolated into a dedicated component and used only when the raw-response dialog is opened.
- A wallet icon is loaded through a lazy loader inside an effect, rather than being imported as a static asset at module scope.
- A no-orders animation is loaded only after hydration and only when no static image override is present.

The shared goal is to avoid paying download and parse cost for code or assets that are not needed on first render.

## Apply / skip gates

### Apply when

- The dependency is only needed for a specific dialog, panel, empty state, or other user-gated UI.
- The feature can render a fallback or placeholder while the optional module loads.
- The code path can be isolated so the heavy import is not required for the rest of the page.
- The feature is not part of the critical first paint or first interaction path.

### Skip when

- The module is required for the initial screen to function.
- There is no safe fallback if the optional dependency fails to load.
- The code path cannot be isolated without changing behavior.
- The dependency is already part of the unavoidable baseline payload for the page.

## Required validation

### `optional_dependency_is_not_imported_at_module_top_level`

**Meaning:** the heavy dependency is not imported directly at the top of the consuming module. Instead, it is introduced through a dedicated lazy loader or a feature-specific component boundary.

**How to validate:**
- Confirm the consumer module imports a local wrapper or hook, not the heavy package itself.
- Confirm the heavy package appears in a separate component or loader module.
- Confirm the top-level module remains usable without executing the optional dependency.

**Evidence-derived example:**
- In `aws/graph-explorer#1349`, `ShowRawResponseDialog.tsx` imports `CodeEditor` from a local component module, while the Monaco package is isolated inside `CodeEditor.tsx`.
- In `cowprotocol/cowswap#6338`, `ConnectWalletContent.tsx` imports `useWalletIcon`, while the asset is loaded inside the hook through a lazy loader.

### `heavy_feature_is_only_loaded_inside_user_gated_code_path`

**Meaning:** the load happens only after a user-gated condition or lifecycle gate, such as opening a dialog, rendering an empty state after hydration, or entering an effect that runs only on mount.

**How to validate:**
- Confirm the load call is inside an effect, callback, or feature-specific component.
- Confirm the feature is not loaded during unrelated renders.
- Confirm the code path is tied to the UI state that actually needs the feature.

**Evidence-derived examples:**
- In `aws/graph-explorer#1349`, Monaco is used only by the raw-response dialog component, which is rendered when the dialog is opened.
- In `cowprotocol/cowswap#6338`, `loadWalletPlusIcon()` runs inside a `useEffect`, so the icon is fetched after mount rather than during module evaluation.
- In `cowprotocol/cowswap#6338`, `loadSurprisedCowAnimation()` runs only when hydration has completed and no static image is provided.

### `fallback_render_path_exists_when_optional_asset_or_module_is_unavailable`

**Meaning:** the component can render without the optional asset or module, and failures are handled without breaking the UI.

**How to validate:**
- Confirm the component can render without the optional asset/module.
- Confirm errors are caught and handled.
- Confirm the UI remains stable while the optional dependency is pending or unavailable.

**Evidence-derived examples:**
- In `cowprotocol/cowswap#6338`, `useWalletIcon()` returns `null` on failure and the icon is omitted from the render path.
- In `cowprotocol/cowswap#6338`, `useNoOrdersAnimation()` returns `null` or `undefined` when loading is skipped or fails, preserving a stable UI.
- In `aws/graph-explorer#1349`, the Monaco wrapper is mocked in tests to avoid runtime script-injection errors, which is consistent with the editor being optional at runtime.

## Recommended approaches

### 1) Wrap the optional dependency in a feature-specific component

The graph-explorer change isolates Monaco into a dedicated `CodeEditor` component and uses it only in the raw-response dialog.

**Good**
```tsx
import { Editor, loader } from "@monaco-editor/react";

loader
  .init()
  .then(monaco => monaco.editor.defineTheme("graph-explorer-light", lightTheme))
  .catch(err => logger.error("Failed to load Monaco editor", err));

export function CodeEditor({
  options,
  ...props
}: ComponentProps<typeof Editor>) {
  return (
    <Editor
      theme="graph-explorer-light"
      options={{
        fontSize: 14,
        scrollBeyondLastLine: false,
        minimap: { enabled: false, ...options?.minimap },
        ...options,
      }}
      {...props}
    />
  );
}
```

**Why this is good:** the Monaco-specific setup is isolated from the dialog module, so the dialog can depend on a local wrapper instead of importing the heavy editor package directly.

### 2) Load optional assets in an effect with cancellation

The cowswap change loads the wallet icon only after mount, and it cancels state updates if the component unmounts first.

**Good**
```tsx
import { useEffect, useState } from "react";
import { loadWalletPlusIcon } from "@cowprotocol/assets/lazy-loaders";

export function useWalletIcon(): string | null {
  const [walletIcon, setWalletIcon] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    void loadWalletPlusIcon()
      .then((icon) => {
        if (!isCancelled) {
          setWalletIcon(icon);
        }
      })
      .catch((error) => {
        if (!isCancelled) {
          console.error("[useWalletIcon] Failed to load wallet icon", error);
          setWalletIcon(null);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  return walletIcon;
}
```

**Why this is good:** the asset is optional, so the UI can render without it while the loader resolves.

### 3) Gate loading on hydration or feature readiness

The no-orders animation is only loaded when the page is hydrated and there is no static image override.

**Good**
```tsx
useEffect(() => {
  if (emptyOrdersImage || !hasHydratedOrders) {
    setAnimationData(undefined);
    return;
  }

  let isCancelled = false;

  async function loadAnimation(): Promise<void> {
    try {
      const animation = await loadSurprisedCowAnimation({ isDarkMode });

      if (!isCancelled) {
        setAnimationData(animation);
      }
    } catch (error) {
      if (!isCancelled) {
        console.error("[useNoOrdersAnimation] Failed to load animation", error);
        setAnimationData(null);
      }
    }
  }

  void loadAnimation();

  return () => {
    isCancelled = true;
  };
}, [emptyOrdersImage, hasHydratedOrders, isDarkMode]);
```

**Why this is good:** the optional payload is not fetched until the UI is ready to use it.

## Anti-patterns

The evidence supports rejecting eager top-level loading of optional feature payloads.

**Bad**
```tsx
import { Editor } from "@monaco-editor/react";
import imageConnectWallet from "@cowprotocol/assets/cow-swap/wallet-plus.svg";
import { loadSurprisedCowAnimation } from "@cowprotocol/assets/lazy-loaders";
```

**Why this is bad:** it makes optional feature code part of the module’s initial dependency graph. The supplied evidence instead shows these payloads being isolated behind a feature-specific component or lazy loader so they are only fetched when the relevant UI path is used.

## How to verify

Use the same measurement family already associated with this strategy:

- bundle size / initial load
- bundle size / initial JS payload
- bundle size / Lighthouse JS payload
- bundle size increase
- perf_flagged

Verification should compare before and after for the affected entrypoint or route:

1. Measure the baseline bundle or payload before the change.
2. Measure again after moving the optional import behind the gated code path.
3. Confirm the optional dependency no longer appears in the initial path.
4. Confirm the relevant UI still renders when invoked.
5. If the repository uses a perf flag, confirm whether the change clears or preserves the flag as expected.

Do not assume a fixed improvement; the evidence only supports directional payload reduction as the intended outcome.

## Evidence and confidence

### Observed facts

- `aws/graph-explorer#1349` adds a dedicated `CodeEditor` wrapper around Monaco and uses it only in the raw-response dialog.
- `aws/graph-explorer#1349` also mocks `@monaco-editor/react` in tests to avoid script injection errors, which is consistent with Monaco being an optional runtime dependency.
- `cowprotocol/cowswap#6338` loads the wallet icon through `useWalletIcon`, which calls a lazy loader in an effect and handles cancellation and errors.
- `cowprotocol/cowswap#6338` loads the no-orders animation through `useNoOrdersAnimation`, gated by hydration state and the presence of a static image.
- `tomasondavis/react_hermes_parser#19` shows a small module extraction pattern, but the supplied patch does not provide direct payload measurement.
- `apollographql/apollo-client#12836` shows bundle-related changes driven by opt-in features, but it is not a direct example of this exact lazy-loading mechanism.

### Inference

- Moving optional imports behind a code path reduces initial payload because the dependency is no longer required for the page’s first execution path.
- Cancellation guards are appropriate when the optional payload is fetched asynchronously and the component may unmount before completion.
- A fallback or null render path is necessary to keep the UI stable while the optional dependency loads or fails.

### Confidence

Confidence is medium: the mechanism is repeated across multiple repositories, but the supplied evidence does not include numeric before/after payload deltas.

## Risks and limitations

- This pattern can shift cost from initial load to first use, so the user may see a delay when opening the gated feature.
- If the optional module is large or has its own transitive dependencies, the first-use experience may still be noticeable.
- Lazy loading requires a stable fallback state; without one, the UI can appear broken or empty.
- Test environments may need explicit mocks for the optional module, as shown by the Monaco test mock.
- The evidence supports this as a payload-reduction strategy, not as a universal performance fix for all CWV regressions.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (5 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **6 observations across 6 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: network-payload--move-optional-dependency-import-behind-a-code-path`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
