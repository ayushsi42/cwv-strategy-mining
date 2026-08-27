---
issue_type: javascript-delivery--component-level-code-splitting-for-optional-ui-controls
parent_strategy: javascript-delivery
risk_tier: low
cwv_metrics:
  - bundle size
  - Lighthouse
  - Lighthouse JavaScript reduction
  - Lighthouse JavaScript payload
source_prs:
  - mieweb/ui#187
  - storyblok/monoblok#246
  - vlossom-ui/vlossom#155
required_validation:
  - optional_entry_point_import_used
  - package_exports_expose_separate_subpath_entry_points
  - optional_dependency_is_declared_for_the_split_entry_point
forbidden_techniques: []
---

# Component-level code splitting for optional UI controls

> **Risk tier:** low · **Parent strategy:** javascript-delivery · **CWV metric:** bundle size, Lighthouse, Lighthouse JavaScript reduction, Lighthouse JavaScript payload

## What this addresses

This strategy reduces JavaScript delivered on the main path by moving optional UI-control logic into separate package entry points and importing only the needed subpath.

The evidence supports two concrete patterns:

1. **Separate optional parser/control entry points**
   - In `storyblok/monoblok#246`, the rich text package export map was expanded to expose `./markdown-parser` and `./html-parser` alongside the main entry.
   - Consumer code was updated to import `markdownToStoryblokRichtext` and `htmlToStoryblokRichtext` from those subpaths instead of the root package.

2. **Keep optional dependencies attached to the split entry point**
   - The same PR added `node-html-parser` as a dependency of the rich text package, consistent with the HTML parser being a separate optional path.
   - In `mieweb/ui#187`, the package added a dedicated `./ozwell` export and marked `@ozwell/react` as an optional peer dependency for that feature path.

**Inference:** when optional feature code is no longer forced through the main package path, consumers that do not use that feature can download and parse less JavaScript.

## When to apply / when to skip

### Apply when
- A package has a core API plus one or more optional controls, parsers, or widgets that are not needed by every consumer.
- The optional feature can be imported independently without changing the core API shape.
- The package can expose a stable subpath export for the optional feature.
- The optional feature has its own dependency surface that should not be forced into the core path.

### Skip when
- The feature is required by nearly every consumer and splitting would only add indirection without reducing delivered JavaScript.
- The code cannot be cleanly separated into a subpath entry point without changing runtime behavior.
- The optional code depends on shared initialization that cannot be isolated safely.
- There is no evidence that consumers import the split path; in that case, the change may not affect delivered payload.

## Required validation

### `optional_entry_point_import_used`
**What to check:** consumer code imports the optional feature from a dedicated subpath rather than from the root package.

**How to validate:**
- Search consumer code for imports of the optional feature.
- Confirm the import path points to the subpath entry point.
- Confirm the root package import is no longer used for that optional feature.

**Evidence-derived examples:**
- `storyblok/monoblok#246`
  - Before: `@storyblok/richtext`
  - After: `@storyblok/richtext/markdown-parser`
  - After: `@storyblok/richtext/html-parser`
- `mieweb/ui#187`
  - Documentation directs consumers to import the widget from `@mieweb/ui/ozwell`.

### `package_exports_expose_separate_subpath_entry_points`
**What to check:** the package export map exposes the optional feature as a distinct subpath entry.

**How to validate:**
- Inspect `package.json` `exports`.
- Confirm the optional feature has its own subpath key.
- Confirm the subpath resolves to its own built artifact.

**Evidence-derived examples:**
- `storyblok/monoblok#246`
  - Added export entries for:
    - `./markdown-parser`
    - `./html-parser`
- `mieweb/ui#187`
  - Added export entry for:
    - `./ozwell`

### `optional_dependency_is_declared_for_the_split_entry_point`
**What to check:** the split feature’s dependency surface is declared so the optional entry point can resolve independently.

**How to validate:**
- Inspect package dependencies and peer dependencies.
- Confirm the optional entry point’s runtime dependency is declared.
- Confirm optionality is expressed where the feature is not universally required.

**Evidence-derived examples:**
- `storyblok/monoblok#246`
  - Added `node-html-parser` to package dependencies for the rich text package.
- `mieweb/ui#187`
  - Declared `@ozwell/react` as an optional peer dependency.

## Recommended approaches

Use a dedicated subpath export for each optional control or parser, and import it only where needed.

### Good: import optional code from a subpath

```ts
import { richTextResolver } from '@storyblok/richtext';
import { markdownToStoryblokRichtext } from '@storyblok/richtext/markdown-parser';
import { htmlToStoryblokRichtext } from '@storyblok/richtext/html-parser';

const markdownDoc = markdownToStoryblokRichtext(markdownSource);
const htmlDoc = htmlToStoryblokRichtext(htmlSource);
const rendered = richTextResolver().render(markdownDoc);
```

### Good: keep optional widgets behind a dedicated entry point

```tsx
import { OzwellWidget } from '@mieweb/ui/ozwell';

export function SupportPanel() {
  return <OzwellWidget apiKey="..." />;
}
```

### Good: expose the optional path in `exports`

```json
{
  "exports": {
    ".": {
      "import": {
        "types": "./dist/index.d.ts",
        "default": "./dist/index.js"
      }
    },
    "./html-parser": {
      "import": {
        "types": "./dist/html-parser.d.ts",
        "default": "./dist/html-parser.js"
      }
    }
  }
}
```

## Anti-patterns

No defensible pre-change anti-pattern regex is supplied by the evidence packet. The supported pattern is the positive one: move optional parser/control code behind separate entry points and import those subpaths directly.

## How to verify

Use the same measurement signals that motivated the change:

- bundle size
- Lighthouse
- Lighthouse JavaScript reduction
- Lighthouse JavaScript payload

### Verification steps
1. Measure the baseline with the optional feature imported from the root package or bundled into the main path.
2. Measure again after moving the feature to a dedicated subpath import.
3. Confirm that the optional feature is no longer part of the main import path.
4. Confirm that the measured JavaScript payload decreases or that Lighthouse reports less JavaScript to parse and execute.

### Verification criteria
- The optional feature is imported from the subpath entry point in consumer code.
- The package export map resolves that subpath independently.
- The optional dependency is declared for the split entry point.
- The before/after measurement is recorded at the package or app entry that consumes the feature.

Do not assume a fixed improvement amount; the supplied evidence reports directional improvements only and does not provide a numeric delta summary.

## Evidence and confidence

### Observed facts
- `storyblok/monoblok#246`
  - Added separate export paths for `./markdown-parser` and `./html-parser`.
  - Updated consumer imports to use those subpaths.
  - Added `node-html-parser` to the package dependencies.
- `mieweb/ui#187`
  - Added a dedicated `./ozwell` export.
  - Marked `@ozwell/react` as an optional peer dependency.
  - Updated documentation to direct consumers to the separate import path.

### Inference
- Moving optional parser/widget code behind separate entry points can reduce the JavaScript that must be loaded and parsed on the main path.
- The strategy is appropriate when the optional feature is not universally needed and can be resolved independently.

### Confidence
- **Medium** overall, because the evidence spans three observations across three repositories with consistent directional improvement, but the supplied measurements do not include numeric deltas.

## Risks and limitations

- Splitting an entry point only helps if consumers actually import the subpath; leaving imports on the root package preserves the larger payload.
- Each optional entry point introduces package surface area that must be documented and maintained.
- Optional dependencies must remain aligned with the split feature; otherwise consumers may encounter resolution failures when using the subpath directly.
- This strategy is about delivery reduction, not runtime behavior changes. It should not be used to justify unrelated refactors or markup changes.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: javascript-delivery--component-level-code-splitting-for-optional-ui-controls`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
