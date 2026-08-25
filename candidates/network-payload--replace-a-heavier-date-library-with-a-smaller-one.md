---
issue_type: network-payload--replace-a-heavier-date-library-with-a-smaller-one
parent_strategy: network-payload
risk_tier: low
cwv_metrics:
  - bundle size
  - Lighthouse JavaScript payload
source_prs:
  - wso2/identity-apps#9366
  - streamlit/streamlit#13071
  - folio-org/stripes-acq-components#928
required_validation:
  - id: date_library_dependency_removed
    description: The heavier date library is removed from the affected dependency manifest(s), and the replacement dependency is added only where the code still needs a library.
  - id: date_library_imports_replaced
    description: Source imports and call sites move from the heavier library to the smaller library or to a local formatter, with equivalent observable behavior preserved.
  - id: date_locale_usage_preserved
    description: Locale initialization and locale imports continue to exist after the swap, using the replacement library’s locale entry points.
forbidden_techniques: []
---

# Replace a heavier date library with a smaller one

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metric:** bundle size, Lighthouse JavaScript payload

## What this addresses

This strategy reduces shipped JavaScript by replacing a heavier date library with a smaller equivalent, or by removing the dependency entirely when the use case is narrow enough for a local formatter.

### Evidence-derived mechanisms

- Replacing `moment` with `dayjs` in application code and package manifests.
- Replacing a single formatting call with a local helper built on `Date` and string padding.
- Preserving locale behavior by updating locale imports and locale-setting calls to the replacement library.
- Updating tests to cover the new helper or the replacement library’s date behavior.

### Inference

The expected CWV effect is lower JavaScript payload, which can reduce download and parse work on initial load.

## When to apply / when to skip

### Apply when

- The codebase imports a heavy date library for formatting, parsing, locale selection, or simple comparisons.
- The replacement library already supports the needed behavior in the repository’s existing usage.
- The date logic is narrow enough that a local formatter can replace the dependency safely.
- You can update tests to prove the same observable date output or validation behavior.

### Skip when

- The date library is used for broad, deeply coupled behavior that is not represented in the evidence.
- The repository does not already demonstrate the replacement mechanism you plan to use.
- The change would require inventing new date APIs, validation rules, or compatibility assumptions.
- The replacement would silently drop locale setup or date validation behavior that the app relies on.

## Required validation

### `date_library_dependency_removed`

**What this means:** The heavier date library must be removed from the relevant dependency manifest(s), not merely left unused in source.

**Evidence:**
- In `wso2/identity-apps#9366`, `moment` was removed from `apps/console/package.json`, `apps/myaccount/package.json`, and the root `package.json`.
- In the same patch, `dayjs` was added where the apps still needed a date library.
- In `folio-org/stripes-acq-components#928`, `moment` was removed from `package.json` and replaced with `dayjs`-based usage through shared components.
- In `streamlit/streamlit#13071`, the `moment` import was removed from the app code, and the timestamp use was replaced with a local helper.

**How to verify:**
- Confirm the affected manifest no longer lists the heavier library.
- Confirm the replacement dependency is present only where the code still needs a library.
- Confirm the source change aligns with the manifest change.

### `date_library_imports_replaced`

**What this means:** Source imports and call sites must move from the heavier library to the smaller one or to a local formatter, while preserving the same observable behavior.

**Evidence:**
- `import * as moment from "moment"` became `import dayjs from "dayjs"` in `wso2/identity-apps#9366`.
- `moment.locale("en")` became `dayjs.locale("en")`.
- `moment.locale(I18n.instance.language)` became `dayjs.locale(I18n.instance.language)`.
- `moment(value, "YYYY-MM-DD", true).isValid()` became `dayjs(value, "YYYY-MM-DD", true).isValid()`.
- `moment().isBefore(value)` became `dayjs().isBefore(value)`.
- `moment().format("YYYY-MM-DD-HH-MM-SS")` became a local `getScreencastTimestamp()` helper in `streamlit/streamlit#13071`.
- `moment.utc(...)` call sites in `folio-org/stripes-acq-components#928` became `dayjs.utc(...)` call sites in date-range query helpers.

**How to verify:**
- Confirm the removed library is no longer imported at the affected call sites.
- Confirm the replacement code still performs the same formatting, parsing, comparison, or timestamp generation.
- Confirm tests cover the observable output or validation behavior.

### `date_locale_usage_preserved`

**What this means:** Locale initialization and locale-specific imports must continue after the replacement.

**Evidence:**
- `moment/locale/si` and `moment/locale/fr` became `dayjs/locale/si` and `dayjs/locale/fr` in `wso2/identity-apps#9366`.
- `moment.locale("en")` became `dayjs.locale("en")`.
- `moment.locale(I18n.instance.language)` became `dayjs.locale(I18n.instance.language)`.

**How to verify:**
- Confirm locale initialization still occurs where it previously did.
- Confirm locale imports are updated to match the replacement library.
- Confirm the replacement does not remove locale behavior that the app depends on.

## Recommended approaches

### 1) Swap the dependency and update direct call sites

Use this when the app still needs a general-purpose date library, but the heavier one is not required.

**Good**
```tsx
import dayjs from "dayjs";
import "dayjs/locale/fr";
import "dayjs/locale/si";

useEffect(() => {
  dayjs.locale("en");
}, []);
```

**Why this is good:** The evidence shows the same locale initialization pattern after the swap, with locale imports updated to the replacement library.

### 2) Replace a narrow formatting use with a local helper

Use this when the date logic is only needed for a specific string format and does not justify a library dependency.

**Good**
```ts
export function getScreencastTimestamp(): string {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");

  return `${year}-${month}-${day}-${hours}-${minutes}-${seconds}`;
}
```

**Why this is good:** In `streamlit/streamlit#13071`, a single timestamp formatting call was replaced by a local helper, and tests were added to verify the output format.

### 3) Preserve validation semantics with replacement-library parsing

Use this when the original code validated date strings or compared dates.

**Good**
```ts
const formattedInitialValue = dayjs(initialValue as string, "YYYY-MM-DD", true);

if (!dayjs(value, "YYYY-MM-DD", true).isValid()) {
  validation.isValid = false;
}
```

**Why this is good:** In `wso2/identity-apps#9366`, strict parsing and validity checks were preserved after the swap, and future-date comparisons were updated to the replacement library.

## Anti-patterns

### Keeping the heavier library after the replacement is already proven

**Bad**
```ts
import * as moment from "moment";

const formattedInitialValue = moment(initialValue as string, "YYYY-MM-DD", true);
```

**Why this is bad:** The evidence shows the heavier library being removed from manifests and source in favor of `dayjs` or a local formatter to reduce shipped JavaScript. Retaining `moment` preserves the larger payload and misses the documented optimization.

## How to verify

Use the same measurement channel already associated with the strategy:

1. Compare bundle size or Lighthouse JavaScript payload before and after the change.
2. Confirm the affected app or package no longer ships the removed date library in the relevant bundle path.
3. Re-run the existing date-focused tests or add equivalent coverage for:
   - locale initialization,
   - strict parsing,
   - date comparison,
   - and any local formatter output.

### Measurable verification examples

- Bundle analysis shows the removed date library no longer appears in the affected app chunk.
- Lighthouse reports a lower JavaScript payload for the affected page after the dependency swap.
- Unit tests pass for:
  - locale-setting behavior,
  - strict date parsing,
  - future-date validation,
  - timestamp formatting.

## Evidence and confidence

### Observed facts

- `wso2/identity-apps#9366` replaced `moment` with `dayjs` in `console` and `myaccount`, updated locale imports, and changed date parsing/comparison call sites.
- `streamlit/streamlit#13071` removed a `moment().format(...)` use and replaced it with a local timestamp helper, with tests added for the helper output.
- `folio-org/stripes-acq-components#928` replaced `moment` with `day.js` in date-range filtering and query-building code, and updated tests to cover timezone-aware behavior.

### Inference

These changes reduce shipped JavaScript by removing a heavier date dependency or by eliminating the dependency entirely for narrow formatting use.

### Confidence

Medium. The evidence is consistent across three repositories and shows the same payload-reduction mechanism, but the measured deltas were not provided.

## Risks and limitations

- Date libraries can differ in parsing strictness, locale handling, and timezone behavior. Preserve the exact observed behavior with tests before removing the old dependency.
- Do not assume a local formatter is sufficient unless the use case is as narrow as the evidence shows.
- If timezone-aware behavior is required, only use the timezone mechanism already evidenced in the repository.
- This strategy is low risk only when the replacement is behaviorally equivalent for the affected call sites.

## Evidence separation

### Evidence
- `moment` was removed from dependency manifests in the supplied patches.
- `dayjs` or a local formatter replaced the removed library at the affected call sites.
- Locale imports and locale-setting calls were updated where locale behavior mattered.
- Tests were added or updated to cover the new behavior.

### Inference
- The payload reduction comes from shipping fewer JavaScript bytes and parsing less date-library code on initial load.