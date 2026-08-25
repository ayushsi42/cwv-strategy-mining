---
issue_type: network-payload--remove-unused-code-from-the-shipped-entry-bundle
parent_strategy: network-payload
risk_tier: low
cwv_metrics: [bundle_size_delta_pct, performance]
source_prs: [vlossom-ui/vlossom#117, storybookjs/storybook#32594, Automattic/wp-calypso#108174]
required_validation:
  - explicit_component_registration_only
  - no_root_package_import_for_tree_shakeable_modules
forbidden_techniques: []
---

# Remove unused code from the shipped entry bundle

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metrics:** `bundle_size_delta_pct`, `performance`

## What this strategy addresses

This strategy reduces shipped JavaScript by preventing unused modules from being pulled into the initial entry bundle.

The evidence supports three related mechanisms:

1. **Limit global component registration**
   - In Vlossom, `createVlossom({ components: VlossomComponents })` registers a component map explicitly.
   - The repository guide states that importing `VlossomComponents` brings all components into the bundle, while importing only the needed components enables tree shaking.
   - The same change adds `component-map.ts` and `component-types.ts`, making the “all components” path explicit and the narrower path available.

2. **Import narrower entrypoints instead of package roots**
   - Storybook replaced root imports from `react-aria` and `react-stately` with narrower submodule imports such as `@react-aria/overlays`, `@react-aria/dialog`, `@react-aria/menu`, `@react-aria/utils`, `@react-stately/menu`, and `@react-stately/tree`.
   - It also switched `react-aria-components` usage to patched per-component entrypoints such as `react-aria-components/patched-dist/Dialog`, `.../Modal`, `.../Popover`, `.../Tabs`, `.../Heading`, and `.../Text`.

3. **Remove unused exported code from shipped modules**
   - In wp-calypso, several exported helpers were deleted when they were no longer needed, including `createOdysseyConfigFromKey`, `inIframe`, `useOpenCommandPalette`, `getPressableShortName`, `getReasonLabelByValue`, and `canUpdateA4AFullyManagedSetting`.
   - This is the same payload-reduction mechanism when dead exports are removed from the shipped surface.

This strategy is about **making the shipped entry bundle smaller by changing what is imported, registered, or exported**. It is not about lazy loading, route splitting, or deferring work to later interaction.

## Evidence summary

### Vlossom UI
- `packages/vlossom/.storybook/preview.ts`
- `packages/vlossom/.storybook-chromatic/preview.ts`
- `packages/vlossom/sandbox/sandbox.ts`
- `packages/vlossom/src/components/component-map.ts`
- `packages/vlossom/src/components/component-types.ts`
- `packages/vlossom/VLOSSOM_USAGE_GUIDE.md`

Observed changes:
- `createVlossom()` became `createVlossom({ components: VlossomComponents })`.
- A full component map was introduced.
- The guide explicitly distinguishes between importing the full component map and importing only the needed components.

### Storybook
- `code/.eslintrc.js`
- `code/core/package.json`
- `code/core/src/components/components/Modal/Modal.tsx`
- `code/core/src/components/components/Modal/Modal.styled.tsx`
- `code/core/src/components/components/Popover/WithPopover.tsx`
- `code/core/src/components/components/Select/Select.tsx`
- `code/core/src/components/components/Tabs/StatelessTab.tsx`
- `code/.yarn/patches/react-aria-components-npm-1.12.2-6c5dcdafab.patch`

Observed changes:
- Root imports from `react-aria` and `react-stately` were replaced with narrower submodule imports.
- `react-aria-components` root imports were replaced with patched per-component entrypoints.
- The ESLint rule was updated to reject broad root imports in favor of narrower entrypoints.

### wp-calypso
- `apps/odyssey-stats/src/lib/create-odyssey-config.ts`
- `apps/wpcom-block-editor/src/utils.js`
- `client/a8c-for-agencies/sections/marketplace/pressable-overview/hooks/use-existing-pressable-plan.ts`
- `client/a8c-for-agencies/sections/marketplace/pressable-overview/lib/get-pressable-short-name.ts`
- `client/components/marketing-survey/cancel-purchase-form/cancellation-reasons.ts`
- `client/dashboard/app/command-palette/README.md`
- `client/dashboard/app/command-palette/utils.ts`
- `client/dashboard/sites/settings-agency/index.tsx`

Observed changes:
- Unused helpers and exports were removed outright from shipped code.

## When to apply / when to skip

### Apply when
- The shipped entry bundle includes modules that are not all needed at startup.
- A package or app imports from a broad root entrypoint when narrower submodule entrypoints exist.
- A component or plugin bootstrap registers a whole catalog, but only a subset is needed for the shipped path.
- A helper or export is no longer consumed and can be removed from the shipped surface.
- Bundle analysis or build output indicates a measurable reduction opportunity in the entry bundle.

### Skip when
- The code path is intentionally “all-in” and the full catalog is required for the shipped experience.
- No evidence-backed narrower entrypoint or export shape exists.
- The change would require speculative refactoring without proof that unused code is excluded from the shipped bundle.
- The goal is to defer work until later interaction; that is a different strategy such as lazy loading or route-level splitting.

## Required validation

### `explicit_component_registration_only`

Validate that the shipped bootstrap or plugin initialization only registers the components intended for the shipped path.

What to check:
- A registration call receives an explicit component map or explicit named imports.
- The code path does not rely on implicit “register everything” behavior unless that is the intended full-bundle mode.
- If a full-map export exists, it is clearly documented as the non-tree-shaken path.

Evidence-derived support:
- Vlossom’s `createVlossom({ components: VlossomComponents })` shows explicit registration.
- The guide states that importing `VlossomComponents` includes all components, while importing only needed components enables tree shaking.

### `no_root_package_import_for_tree_shakeable_modules`

Validate that tree-shakeable dependencies are imported from narrower entrypoints rather than package roots.

What to check:
- Root imports are replaced with submodule imports where the patch shows a supported narrower path.
- The chosen entrypoint matches the evidence, such as `@react-aria/overlays`, `@react-aria/dialog`, `@react-aria/menu`, `@react-stately/menu`, `@react-stately/tree`, or `react-aria-components/patched-dist/<Component>`.
- The import change is consistent with the package’s tree-shaking guidance or patching approach.

Evidence-derived support:
- Storybook’s ESLint rule explicitly rejects root imports from `react-aria`, `react-stately`, and `react-aria-components` in favor of narrower submodules or patched component entrypoints.

## Recommended approaches

### 1) Register only the components needed by the shipped path

Use explicit component registration instead of importing a full component catalog when the startup path does not need every component.

```ts
import { createApp } from 'vue';
import { createVlossom, VsAvatar, VsButton } from 'vlossom';
import App from './App.vue';

const app = createApp(App);

app.use(
  createVlossom({
    components: { VsAvatar, VsButton },
    theme: 'dark',
    colorScheme: { VsButton: 'blue' },
  }),
);

app.mount('#app');
```

This is the evidence-backed good shape because it keeps the shipped registration surface limited to the components actually referenced.

### 2) Prefer narrower submodule imports over package-root imports

When a dependency exposes tree-shakeable submodules, import the specific submodule used by the component.

```ts
import { useInteractOutside } from '@react-aria/interactions';
import { Overlay, useOverlay, useOverlayPosition } from '@react-aria/overlays';
import { useOverlayTriggerState } from '@react-stately/overlays';
```

This matches the Storybook patch pattern and avoids pulling a broader root package surface into the bundle.

### 3) Use patched per-component entrypoints when the package root is too broad

```ts
import { Dialog } from 'react-aria-components/patched-dist/Dialog';
import { ModalOverlay, Modal as ModalUpstream } from 'react-aria-components/patched-dist/Modal';
import { Tab } from 'react-aria-components/patched-dist/Tabs';
```

This is supported by the evidence where Storybook moved from root imports to patched component entrypoints optimized for tree shaking.

### 4) Remove dead exports when they are no longer part of the shipped surface

If a helper is no longer consumed, delete it rather than keeping it in the shipped module.

```ts
export default function createOdysseyConfigFromConfigData(configData: ConfigData) {
  const configApi = new ConfigApi();
  configApi.setConfigData(configData);
  return configApi;
}
```

This reflects the same mechanism shown by wp-calypso removing unused helpers and leaving only the needed exported entrypoint.

## Anti-patterns

The evidence is sufficient to reject broad root imports and implicit “register everything” patterns, but it is **not** sufficient to define a universal bad-code regex beyond the documented import shapes. Therefore, no additional forbidden technique patterns are asserted here.

## How to verify

Use the same measurement family already present in the evidence:

- Compare `bundle_size_delta_pct` before and after the change.
- Check the associated `performance` signal used by the repository’s measurement process.
- If the repository reports bundle-size or Lighthouse JS payload metrics, compare those same metrics before and after; do not substitute a different metric family.

Verification should answer:
- Did the shipped entry bundle exclude the unused modules after the change?
- Did the measured bundle-size delta move in the expected direction?
- Did the performance signal improve, remain flat, or regress?

Do not promise a fixed improvement. The evidence supports that this strategy often reduces payload, with observed positive and negative outcomes.

## Evidence and confidence

### Observed facts
- **Vlossom UI**: `createVlossom({ components: VlossomComponents })` was introduced, and the repository documentation explicitly states that importing `VlossomComponents` includes all components while importing only needed components enables complete tree shaking.
- **Storybook**: root imports from `react-aria` and `react-stately` were replaced with narrower submodule imports; `react-aria-components` root imports were replaced with patched per-component entrypoints.
- **wp-calypso**: several unused helpers and exports were deleted outright from shipped code.

### Inference
- These changes all serve the same payload-reduction mechanism: reduce the entry bundle by narrowing the import/export surface so bundlers can exclude unused code.
- The strategy is appropriate when the shipped path can be expressed with explicit imports or registrations and when the dependency/package structure supports tree shaking.

### Confidence
High. The supplied evidence includes documentation, code patches, and multiple independent repositories showing the same mechanism.

## Risks and limitations

- Importing a full component map or root package entrypoint can intentionally pull more code into the bundle; that is acceptable only when the full surface is required.
- Some packages may not expose narrower entrypoints for every symbol; in that case, this strategy should not be forced without evidence.
- Deleting exports can break consumers if the symbol is part of a public API; only remove exports when the evidence shows they are unused or intentionally replaced.
- Patched package entrypoints may require maintenance when upstream adds new components or changes internal structure.
- This strategy reduces shipped payload, but it is not a substitute for lazy loading when the code is genuinely non-initial and can be deferred.