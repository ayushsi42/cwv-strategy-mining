---
issue_type: barrel-imports
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
required_validation: []
forbidden_techniques: []
source_prs:
- coveo/ui-kit#3011
- jellyfin/jellyfin-web#5238
- jellyfin/jellyfin-web#5990
- jellyfin/jellyfin-web#6393
---
# Barrel imports

> **Risk tier:** medium · **Applies to:** EDS, CS, Headless

## What this addresses

For runtime values, use an exact module path when the installed package provides one and the path has been verified. The cited PRs specifically replace broad generated-client or SDK imports with direct imports to help tree-shaking.

## When to apply / when to skip
**Apply when:**
- A runtime value is imported from a broad SDK, generated-client, or `index.ts` entry point.
- The imported identifier is a runtime value, such as an enum or API helper.
- The installed package version contains a verified direct module path for that identifier.
- The affected application bundle is known.

**Skip when:**
- The import is type-only, unless the package requires a direct type path.
- The package version or direct module path cannot be verified.
- The change would require modifying generated SDK source rather than updating an application import.

## Recommended approaches

### EDS: import a runtime value from its exact SDK module

Use a block-relative module path for a runtime value when that path is verified in the SDK source copied or generated for the block.

```javascript
export default async function decorate(block) {
  const { BaseItemKind } = await import('./jellyfin/models/base-item-kind.js');
  const item = JSON.parse(block.textContent);

  const isSupported = [
    BaseItemKind.Series,
    BaseItemKind.Season,
    BaseItemKind.Episode,
  ].includes(item.Type);

  block.dataset.supportedItemType = isSupported;
}
```

The cited Jellyfin change replaces a generated-client barrel import with direct imports for `BaseItemKind` and `SeriesStatus`.

### CS: replace a verified barrel import in client-side JavaScript

List exact generated SDK files in the client library and expose only the runtime values needed by the client-side behavior.

```xml
<!-- ui.apps/src/main/content/jcr_root/apps/example/clientlibs/site-jellyfin/.content.xml -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:cq="http://www.day.com/jcr/cq/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.site.jellyfin]"
    js="[models/process-priority-class.js,models/trickplay-scan-behavior.js,priority-settings.js]"/>
```

```javascript
// priority-settings.js
(function () {
  const { ProcessPriorityClass, TrickplayScanBehavior } = window.JellyfinModels;

  window.ExampleJellyfinSettings = {
    ProcessPriorityClass,
    TrickplayScanBehavior,
  };
}());
```

The cited Jellyfin change uses direct per-model imports for these runtime values to help tree-shaking.

### Headless: import the exact API helper used by the route

Keep the SDK-specific import in a local adapter so the route imports an application module rather than a broad SDK entry point.

```javascript
// lib/jellyfin/system-api.js
export async function loadServerLogs(api, options) {
  const response = await api.system.getServerLogs(options);

  return response.data;
}
```

```javascript
// routes/server-logs.js
import { loadServerLogs } from '../lib/jellyfin/system-api.js';

export async function getServerLogs(api, options) {
  return loadServerLogs(api, options);
}
```

The cited Jellyfin change imports `getSystemApi` from its direct SDK module.

## Anti-patterns

### Importing runtime SDK values from a generated-client barrel

```javascript
// EDS block: Bad — broad local generated-client barrel.
export default async function decorate(block) {
  const {
    BaseItemKind,
    ProcessPriorityClass,
    TrickplayScanBehavior,
  } = await import('./jellyfin/generated-client/index.js');

  block.dataset.itemKind = BaseItemKind.Series;
  block.dataset.priority = ProcessPriorityClass.Normal;
  block.dataset.trickplay = TrickplayScanBehavior.FullScan;
}
```

```javascript
// CS clientlib: Bad — generated-client barrel bundled as one clientlib source.
(function () {
  const {
    BaseItemKind,
    ProcessPriorityClass,
    TrickplayScanBehavior,
  } = window.JellyfinGeneratedClient;

  window.ExampleJellyfinSettings = {
    BaseItemKind,
    ProcessPriorityClass,
    TrickplayScanBehavior,
  };
}());
```

```javascript
// Headless adapter: Bad — broad generated-client entry point.
import {
  BaseItemKind,
  ProcessPriorityClass,
  TrickplayScanBehavior,
} from '../generated/jellyfin/index.js';
```

**Why this is bad:** The cited PRs replace this style of runtime import with exact per-model imports to help tree-shaking.

### Importing an API helper through a broad SDK entry point

```javascript
// EDS block: Bad — broad SDK helper barrel.
export default async function decorate(block) {
  const { getSystemApi } = await import('./jellyfin/utils/index.js');
  const api = window.jellyfinApi;

  block.textContent = JSON.stringify(
    await getSystemApi(api).getServerLogs(),
  );
}
```

```javascript
// CS clientlib: Bad — broad helper bundle exposes every SDK helper.
(function () {
  const { getSystemApi } = window.JellyfinSdkUtils;
  const api = window.jellyfinApi;

  window.ExampleServerLogs = function loadServerLogs(options) {
    return getSystemApi(api).getServerLogs(options);
  };
}());
```

```javascript
// Headless adapter: Bad — broad local SDK helper entry point.
import { getSystemApi } from '../generated/jellyfin/utils/index.js';
```

**Why this is bad:** The cited logs migration uses the direct `getSystemApi` module rather than a broad helper entry point.

### Guessing an undocumented package path

```javascript
// EDS block: Bad — do not use an unverified internal module path.
export default async function decorate(block) {
  const { BaseItemKind } = await import(
    './content-sdk/dist/internal/models/base-item-kind.js'
  );

  block.dataset.itemKind = BaseItemKind.Series;
}
```

```javascript
// CS clientlib: Bad — do not add an unverified internal SDK file to js[].
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:cq="http://www.day.com/jcr/cq/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.site.content-sdk]"
    js="[content-sdk/dist/internal/models/base-item-kind.js]"/>
```

```javascript
// Headless adapter: Bad — undocumented internal SDK module path.
import { BaseItemKind } from '../content-sdk/dist/internal/models/base-item-kind.js';
```

**Why this is bad:** Use only paths verified for the installed package version.

## Flavor-specific notes

### EDS

Apply the change in the JavaScript module that imports the runtime SDK value. Verify the direct path against the installed package version.

### CS

Apply the change in the client-side JavaScript source that imports the runtime SDK value. Verify the direct path against the installed package version.

### Headless

Apply the change in the client-rendered route, component, or SDK adapter that imports the runtime value or API helper. Verify the direct path against the installed package version.