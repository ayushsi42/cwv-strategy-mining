---
issue_type: icon-payload-bloat
risk_tier: medium
forbidden_techniques:
- pattern: from\s*['"]react-icons(?:/[^/'"]+)?['"]
  reason: Don't import from the react-icons package or an icon-set barrel when bundle
    analysis shows it retains unnecessary icon code; use a verified per-icon entrypoint
    instead.
- pattern: from\s*['"]@patternfly/react-icons['"]
  reason: Don't import from the PatternFly icon package root when the production build
    retains unnecessary icons; use a verified per-icon entrypoint instead.
- pattern: from\s*['"]@styled-icons/[^/'"]+['"]
  reason: Don't import from a styled-icons family barrel when it causes the build
    to retain unnecessary icon modules; use a verified icon subpath instead.
applicable_flavors:
- eds
- cs
- ams
- headless
required_validation: []
source_prs:
- apache/superset#36050
- ONEARMY/community-platform#1547
- RedHatInsights/landing-page-frontend#420
- boostcampwm-2022/web07-zokboo.com#233
- opencollective/opencollective-frontend#8664
- LifeSG/react-design-system#190
- skbkontur/db-viewer#80
- woowacourse/perf-basecamp#79
- woowacourse/perf-basecamp#90
- openshift-assisted/assisted-installer-ui#2447
- woowacourse/perf-basecamp#120
- commercetools/ui-kit#3014
---
# Icon payload bloat

> **Risk tier:** medium

## What this addresses

Icon-library barrel imports can retain unnecessary icon code in a bundle even when a page uses only a few icons. The evidence PRs show projects reducing bundle size or development module counts by switching from package or icon-family barrels to per-icon entrypoints.

## When to apply / when to skip
**Apply when:**
- Bundle analysis attributes meaningful parsed or transferred JavaScript to an icon package or icon-family barrel.
- The installed icon package provides per-icon entrypoints that resolve in the repository's production build.
- The changed icon renders correctly after the import change.

**Skip when:**
- Production bundle analysis confirms that the current package and build already remove unused icons effectively.
- The available deep-import path is undocumented or fails the production build.
- The icon is part of a third-party component whose package boundary cannot be changed safely.

## Recommended approaches

### Use verified per-icon package entrypoints

Import individual icons from package paths that correspond to a single icon rather than from an icon-family or package-root barrel. The exact path depends on the package version and its published entrypoints.

```javascript
// Good: PatternFly per-icon path
import { ExclamationCircleIcon } from '@patternfly/react-icons/dist/js/icons/exclamation-circle-icon';
```

```javascript
// Good: styled-icons per-icon path
import { ChevronDown } from '@styled-icons/boxicons-regular/ChevronDown';
import { ChevronUp } from '@styled-icons/boxicons-regular/ChevronUp';
```

```javascript
// Good: react-icons all-files per-icon paths
import { MdClose } from '@react-icons/all-files/md/MdClose';
import { MdSearch } from '@react-icons/all-files/md/MdSearch';
```

Some projects enforce these paths with ESLint restrictions so future imports do not reintroduce package-root or icon-family imports.

### Provide individual package entrypoints for internally maintained icons

For an internally maintained icon package, expose each icon through its own entrypoint so consuming applications can import only the icons they use.

```javascript
// Good: consumer imports a single generated icon entrypoint
import AngleDownReact from '@commercetools-uikit/icons/generated/AngleDownReact';
```

The evidence PR for this approach reports that unique icon entrypoints enabled better tree shaking in consuming applications and reduced measured bundle sizes.

## Anti-patterns

### Importing an icon-family barrel

```javascript
// Bad: imports from an icon-family barrel
import { ChevronDown, ChevronUp, Search } from '@styled-icons/boxicons-regular';
```

### Importing an icon-set barrel

```javascript
// Bad: imports from an icon-set barrel rather than a verified per-icon module
import { MdClose, MdSearch, MdMenu } from 'react-icons/md';
```

### Replacing a verified per-icon path with the package root

```javascript
// Bad: imports from the package root instead of a verified per-icon entrypoint
import { ExclamationCircleIcon } from '@patternfly/react-icons';
```

## Verification

- Compare production bundle analysis before and after the import changes.
- Confirm that every per-icon import path resolves with the installed package version.
- Render affected screens and confirm the expected icons are present.
- Consider lint rules that prohibit package-root and icon-family barrel imports where those imports have caused bundle retention.