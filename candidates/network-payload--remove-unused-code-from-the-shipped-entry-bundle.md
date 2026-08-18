---
issue_type: network-payload--remove-unused-code-from-the-shipped-entry-bundle
parent_strategy: network-payload
risk_tier: low
cwv_metrics: [bundle_size_delta_pct]
source_prs: [Jujulego/jill#1258, ant-design/ant-design#55179, ant-design/x#1198]
required_validation:
  - shipped_entry_bundle_contains_no_manual_chunk_for_removed_code
  - runtime_dependency_is_not_referenced_by_the_shipped_entry_bundle
  - locale_module_is_re_exported_from_the_shared_locale_entry
forbidden_techniques: []
---

# Remove unused code from the shipped entry bundle

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metric:** `bundle_size_delta_pct`

## Summary

This strategy applies when code that is currently shipped in the entry bundle can be removed without changing supported runtime behavior. The supplied evidence supports three removal patterns:

1. **Remove packaging-only chunking** for code that no longer needs to be isolated into a separate shipped chunk.
2. **Remove unused runtime imports or calls** from the shipped entry path.
3. **Split locale data into per-language modules and re-export it through the shared locale entry** so the public locale surface stays stable while the shipped payload is reduced.

The measured outcome in the evidence is a reduction in shipped JavaScript payload, tracked by `bundle_size_delta_pct`.

## Apply / Skip gates

### Apply when
- The shipped entry bundle contains code that is not required for the supported runtime path.
- A dependency is imported only for a call site that can be removed without changing supported behavior.
- Locale data is duplicated across entry points and can be factored into a dedicated locale module with a shared re-export.
- A manual chunk exists only to package code that is no longer needed in the shipped entry.

### Skip when
- The code is still required by the shipped entry path.
- Removing the dependency would change supported behavior or remove a public runtime capability.
- The split would add indirection without reducing shipped code.
- The shared locale entry would no longer remain the consumer-facing access point after the change.

## Required validation

### `shipped_entry_bundle_contains_no_manual_chunk_for_removed_code`
**What it checks:** The shipped entry bundle no longer contains a packaging-only manual chunk for code that was removed from the entry path.

**Why it matters:** If the removed code is still isolated into a manual chunk, the shipped bundle may still carry unnecessary packaging overhead.

**Evidence:** In `Jujulego/jill#1258`, `rollup.config.js` removed the `manualChunks` entry for `parser`, indicating that the parser code was no longer being split out as a separate shipped chunk.

### `runtime_dependency_is_not_referenced_by_the_shipped_entry_bundle`
**What it checks:** The shipped entry path no longer imports or calls the removed runtime dependency.

**Why it matters:** A dependency that is still referenced by the entry bundle remains part of the shipped payload.

**Evidence:** In `Jujulego/jill#1258`, `src/main.ts` removed `captureMessage` from `@sentry/node`, while preserving the rest of the CLI flow.

### `locale_module_is_re_exported_from_the_shared_locale_entry`
**What it checks:** A locale is defined in a dedicated module and then included through the shared locale registry or aggregate locale entry.

**Why it matters:** This preserves the public locale import surface while allowing locale code to be organized and shipped more efficiently.

**Evidence:** In `ant-design/ant-design#55179`, `components/date-picker/locale/mr_IN.ts`, `components/time-picker/locale/mr_IN.ts`, and `components/locale/mr_IN.ts` show the split-and-re-export pattern.

## Evidence-derived implementation patterns

### 1) Remove packaging-only chunking when the code is no longer needed

**Good**
```js
// rollup.config.js
const options = {
  output: {
    sourcemap: true,
    chunkFileNames: '[name].js',
    generatedCode: 'es5',
  },
  plugins: [
    nodeResolve({ exportConditions: ['node'] }),
  ],
};
```

**Evidence basis:** `Jujulego/jill#1258` removed the `manualChunks` entry for `parser`.

**Bad**
```js
// Keeps a packaging-only split for code that is no longer needed in the shipped entry
const options = {
  output: {
    sourcemap: true,
    chunkFileNames: '[name].js',
    generatedCode: 'es5',
    manualChunks: {
      parser: ['./src/cli/parser.js'],
    },
  },
};
```

### 2) Remove unused runtime calls from the shipped entry path

**Good**
```ts
import { captureException, startSpan } from '@sentry/node';

void startSpan({ name: 'jill', op: 'cli.main', attributes: { 'cli.argv': argv } }, () =>
  parser
    .wrap(parser.terminalWidth())
    .fail((msg, err) => {
      const logger = inject$(LOGGER);

      if (msg) {
        logger.error(msg);
      } else if (err instanceof ClientError) {
        logger.warning(err.message);
      } else {
        captureException(err);
      }
    }),
);
```

**Evidence basis:** `Jujulego/jill#1258` removed `captureMessage` from the CLI entry path while keeping the rest of the flow intact.

**Bad**
```ts
import { captureException, captureMessage, startSpan } from '@sentry/node';

void startSpan({ name: 'jill', op: 'cli.main', attributes: { 'cli.argv': argv } }, () =>
  parser
    .wrap(parser.terminalWidth())
    .fail((msg, err) => {
      const logger = inject$(LOGGER);

      if (msg) {
        logger.error(msg);
        captureMessage(msg, { level: 'error' });
      } else if (err instanceof ClientError) {
        logger.warning(err.message);
      } else {
        captureException(err);
      }
    }),
);
```

### 3) Split locale data into per-language modules and re-export through the shared locale entry

**Good**
```ts
// components/date-picker/locale/mr_IN.ts
import CalendarLocale from '@rc-component/picker/lib/locale/mr_IN';
import TimePickerLocale from '../../time-picker/locale/mr_IN';
import type { PickerLocale } from '../generatePicker';

const locale: PickerLocale = {
  lang: {
    placeholder: 'दिनांक निवडा',
    yearPlaceholder: 'वर्ष निवडा',
    quarterPlaceholder: 'तिमाही निवडा',
    monthPlaceholder: 'महिना निवडा',
    weekPlaceholder: 'आठवडा निवडा',
    rangePlaceholder: ['प्रारंभ तारीख', 'शेवटची तारीख'],
    ...CalendarLocale,
  },
  timePickerLocale: {
    ...TimePickerLocale,
  },
};

export default locale;
```

```ts
// components/locale/mr_IN.ts
import Pagination from '@rc-component/pagination/lib/locale/mr_IN';

import type { Locale } from '.';
import Calendar from '../calendar/locale/mr_IN';
import DatePicker from '../date-picker/locale/mr_IN';
import TimePicker from '../time-picker/locale/mr_IN';

const localeValues: Locale = {
  locale: 'mr',
  DatePicker,
  TimePicker,
  Calendar,
  Pagination,
};

export default localeValues;
```

**Evidence basis:** `ant-design/ant-design#55179` added `mr_IN` locale modules and registered them through the shared locale list.

**Bad**
```ts
// Locale defined only in a feature module and not re-exported through the shared locale entry
export default {
  locale: 'mr',
  DatePicker: { /* ... */ },
  TimePicker: { /* ... */ },
};
```

## Verification

Use `bundle_size_delta_pct` as the primary measurable check.

### Minimum verification steps
1. Measure the shipped entry bundle before the change.
2. Apply the removal or factoring change.
3. Measure the shipped entry bundle again.
4. Confirm the delta moves in the expected direction for the change.

### Validation-specific checks
- For `shipped_entry_bundle_contains_no_manual_chunk_for_removed_code`:
  - confirm the removed code is no longer isolated into a manual chunk in the shipped build configuration.
- For `runtime_dependency_is_not_referenced_by_the_shipped_entry_bundle`:
  - confirm the shipped entry path no longer imports or calls the removed dependency.
- For `locale_module_is_re_exported_from_the_shared_locale_entry`:
  - confirm the locale exists in a dedicated module and is reachable through the shared locale entry.

## Evidence and inference

### Observed facts
- `Jujulego/jill#1258` removed a `manualChunks` entry for `parser` and removed `captureMessage` from the CLI entry path.
- `ant-design/ant-design#55179` added `mr_IN` locale modules and registered them through the shared locale list.
- `ant-design/x#1198` removed unused dependencies from `packages/x-markdown/package.json` and refactored animation code away from `@react-spring/web`, with a reported `bundle_size_delta_pct` improvement.

### Inference
- Removing unused shipped code reduces the JavaScript payload that consumers must load.
- Locale factoring is a safe payload-reduction pattern when the shared locale entry remains the public access point.
- The same mechanism can apply across repositories when the code shape matches the evidence.

## Confidence

**Medium**, based on three observations across three repositories with consistent improvement direction and no regressions in the supplied evidence.

## Risks and limitations

- Removing code from the shipped entry bundle can break behavior if the code is still required indirectly.
- Splitting locale or feature data can introduce import-path mistakes if the shared re-export is not updated consistently.
- The evidence supports removal and factoring patterns, not a universal rule for all unused-looking code.
- The exact bundle-size improvement is repository- and build-dependent; verify with measurement rather than assuming a fixed percentage.