---
issue_type: network-payload--remove-unused-dependency-from-shipped-bundle
parent_strategy: network-payload
risk_tier: low
cwv_metrics: [bundle_size_delta_pct]
source_prs: [kunokdev/react-window-size-listener#30, akash-network/console#2419, openstreetmap/openstreetmap-website#6996, balena-io/balena-sdk#1563]
required_validation:
  - browser_bundle_excludes_unused_dependency
  - shipped_code_uses_local_or_builtin_replacement
forbidden_techniques: []
---

# Remove unused dependency from shipped bundle

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metric:** `bundle_size_delta_pct`

## What this strategy does

This strategy reduces browser payload by removing dependency code that does not need to ship to the client, or by replacing that dependency with a smaller local or built-in implementation.

The evidence supports four related mechanisms:

1. removing a dependency from package metadata and bundle inputs so it no longer ships to the browser
2. excluding browser-unneeded modules from the browser bundle
3. replacing a dependency-backed operation with a local implementation
4. splitting browser and non-browser helpers so server-only file APIs stay out of browser delivery

The measured CWV-related signal supplied in the evidence is `bundle_size_delta_pct`. No other metric is required by the packet.

## Apply / skip gates

### Apply when

- a dependency is present in the shipped browser bundle but is not required at runtime in the browser
- the same behavior can be implemented with a smaller local helper or a built-in/browser-appropriate API
- the code path is server-only, file-path-only, or otherwise not meant for browser delivery
- the build pipeline can exclude or externalize the dependency from the browser artifact

### Skip when

- the dependency is required for browser runtime behavior
- the replacement changes semantics beyond what the evidence supports
- the dependency is removed from package metadata but still referenced by shipped code
- the only replacement is speculative and not backed by a patch showing equivalent behavior

## Required validations

### `browser_bundle_excludes_unused_dependency`

**What this validation checks:** the browser-shipped bundle no longer includes the unused dependency or module.

**Evidence-backed examples:**

- `balena-io/balena-sdk#1563` excludes `mime` and `fs/promises` from the browser bundle task.
- `kunokdev/react-window-size-listener#30` removes `lodash.debounce` from dependencies and rewrites the shipped implementation so the dependency is no longer needed.
- `openstreetmap/openstreetmap-website#6996` removes `leaflet.polyline` from the asset pipeline and from the main JS manifest.

**Pass criteria:**

- the dependency is removed from the browser bundle graph, manifest, or packaging step
- the shipped browser artifact no longer imports or includes that dependency
- any replacement is loaded only where needed

### `shipped_code_uses_local_or_builtin_replacement`

**What this validation checks:** the removed dependency’s behavior is replaced by local code, a built-in API, or a browser-appropriate split module.

**Evidence-backed examples:**

- `akash-network/console#2419` replaces `semver` usage with a local `compareVersions()` helper and string normalization.
- `balena-io/balena-sdk#1563` adds separate browser and non-browser helper modules for file-path and MIME handling.
- `openstreetmap/openstreetmap-website#6996` replaces `L.PolylineUtil.decode(...)` with `OSM.decodePolyline(...)` backed by a different decoder path.

**Pass criteria:**

- the replacement is present in source
- the replacement covers the same use case as the removed dependency
- browser code does not import server-only modules that would reintroduce the payload

## Recommended implementation patterns

### 1) Remove the dependency from browser bundle inputs

Use this when the dependency is no longer needed in browser delivery.

**Good evidence-derived example:**

```js
gulp.task('pack-browser', function () {
  const bundle = browserify('./index.js')
    .exclude('fs')
    .exclude('path')
    .exclude('balena-settings-client')
    .exclude('mime')
    .exclude('fs/promises')
    .bundle();

  return bundle;
});
```

**Why this is valid:** `balena-io/balena-sdk#1563` shows browser bundling exclusions for modules that should not ship to the client.

### 2) Replace dependency-backed logic with a local helper

Use this when the dependency only provides a narrow utility and the local implementation is equivalent for the supported use case.

**Good evidence-derived example:**

```ts
function compareVersions(a: string, b: string): number {
  const partsA = a.split(".").map(Number);
  const partsB = b.split(".").map(Number);
  const maxLength = Math.max(partsA.length, partsB.length);

  for (let i = 0; i < maxLength; i++) {
    const partA = partsA[i] ?? 0;
    const partB = partsB[i] ?? 0;
    if (partA > partB) return 1;
    if (partA < partB) return -1;
  }

  return 0;
}
```

**Why this is valid:** `akash-network/console#2419` removes `semver` and uses a local comparator for version ordering.

### 3) Split browser and non-browser helpers

Use this when the dependency is only needed for file-path or Node APIs.

**Good evidence-derived example:**

```ts
export const assetHelpers = {
  getMimeType: (filePath: string): string => {
    return getType(filePath) ?? 'application/octet-stream';
  },

  getFileSize: async (filePath: string): Promise<number> => {
    const stats = await fs.stat(filePath);
    return stats.size;
  },

  readFileChunk: async (filePath: string, offset: number, length: number) => {
    const fd = await fs.open(filePath, 'r');
    try {
      const buffer = Buffer.alloc(length);
      const { bytesRead } = await fd.read(buffer, 0, length, offset);
      return buffer.subarray(0, bytesRead);
    } finally {
      await fd.close();
    }
  },
};
```

```ts
const filePathUploadNotImplementedForBrowser = () => {
  throw new Error('File path uploads are not supported in the browser.');
};

export const assetHelpers = {
  getMimeType: filePathUploadNotImplementedForBrowser,
  getFileSize: filePathUploadNotImplementedForBrowser,
  readFileChunk: filePathUploadNotImplementedForBrowser,
};
```

**Why this is valid:** `balena-io/balena-sdk#1563` separates browser and non-browser helper modules so server-only dependencies stay out of browser delivery.

## Good / bad examples

### Good: remove a browser-only dependency from the bundle

- remove the dependency from the browser packaging step
- replace the behavior with a local helper or built-in API
- keep browser code free of server-only imports

This is supported by:
- `balena-io/balena-sdk#1563`
- `akash-network/console#2419`

### Good: replace a small utility dependency with local code

- use a local comparator, parser, or formatter when the dependency only covered a narrow function
- verify the replacement preserves the supported behavior

This is supported by:
- `akash-network/console#2419`

### Good: split browser and server helpers

- keep file-system or MIME logic in a non-browser module
- provide a browser stub or browser-safe alternative

This is supported by:
- `balena-io/balena-sdk#1563`

### Bad: remove the dependency from `package.json` but leave shipped imports intact

- the browser bundle still includes the code
- payload does not meaningfully shrink

### Bad: replace a dependency with a larger or broader library

- the shipped payload may stay the same or grow
- the change no longer matches the strategy

### Bad: move server-only code into browser delivery

- browser bundle size increases
- unsupported APIs may break runtime behavior

## Verification

Use the supplied metric: `bundle_size_delta_pct`.

### Measurable verification steps

1. Measure the browser bundle size before the change.
2. Apply the dependency removal, exclusion, or local replacement.
3. Measure the browser bundle size after the change.
4. Compute `bundle_size_delta_pct`.
5. Confirm the browser artifact no longer contains the removed dependency or module.

### What to record

- bundle size before
- bundle size after
- `bundle_size_delta_pct`
- the exact dependency or module removed
- the replacement path used, if any

### Expected outcome

The evidence supports a reduction in shipped bytes when the dependency was truly unused in browser delivery. The change may be neutral if the dependency was already excluded or if the replacement adds similar weight.

## Evidence summary

### Observed facts

- `kunokdev/react-window-size-listener#30` removes `lodash.debounce` and rewrites the shipped implementation as a TypeScript hook with built-in debouncing and SSR-safe checks.
- `akash-network/console#2419` removes `semver` and replaces it with a local version comparator.
- `openstreetmap/openstreetmap-website#6996` removes a shipped polyline asset and switches to a different decoder path.
- `balena-io/balena-sdk#1563` excludes `mime` and `fs/promises` from browser bundling and adds browser/server helper separation.

### Inference

- The common mechanism is payload reduction by removing dependency code from shipped browser artifacts, either by exclusion or by local replacement.
- The strategy is low risk when the removed dependency is not needed in browser runtime and the replacement is behaviorally equivalent for the supported use case.

### Confidence

High. The evidence is directionally consistent across multiple repositories and shows both direct dependency removal and browser-specific exclusion/replacement patterns.