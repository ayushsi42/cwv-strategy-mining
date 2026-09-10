---
issue_type: javascript-payload
forbidden_techniques: []
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
required_validation: []
source_prs:
- vazco/uniforms#993
- rudolfdeer/youtube-client#1
- prgrms-web-devcourse/Team-Books-CheckMoi-FE#18
- charmverse/app.charmverse.io#794
- wso2/oxygen-ui#31
- SeleniumHQ/selenium-ide#1622
- ShoanRohan/Psagot#150
---
# JavaScript payload

## What this addresses

The evidence PRs discuss MUI import syntax intended to be tree-shakeable, such as:

```javascript
import Pagination from '@mui/material/Pagination';
import Table from '@mui/material/Table';
import Stack from '@mui/material/Stack';
```

One PR also notes that a Next.js transformation can map:

```javascript
import { Dialog } from '@mui/material';
```

to a tree-shaking-friendly format.

The evidence does not include production bundle measurements or CWV measurements. Verify the emitted production bundle before concluding that an import change reduces JavaScript payload.

## When to apply / when to skip
**Apply when:**
- A MUI component can be imported through its documented component entry point.
- Production bundle inspection confirms that the change affects the emitted JavaScript as intended.
- The affected UI is verified after the import change.

**Skip when:**
- The project build transform already converts barrel imports into a tree-shaking-friendly form.
- Production output does not show a meaningful change.
- The required import path is not supported by the installed library version.

## Recommended approaches

### Use MUI component entry points

Use component-level MUI imports where appropriate:

```javascript
import Pagination from '@mui/material/Pagination';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
```

```javascript
import Stack from '@mui/material/Stack';
```

The evidence PRs identify these as tree-shakeable import syntax. Confirm the production artifact, because source import style alone does not demonstrate a payload reduction.

### Account for framework import transforms

Some projects may configure a framework transform that rewrites barrel imports into tree-shaking-friendly imports:

```javascript
import { Dialog } from '@mui/material';
```

If such a transform is present, inspect the emitted production output before changing imports solely for payload reasons.

## Anti-patterns

### Assuming a barrel import necessarily increases the production bundle

```javascript
import { Dialog } from '@mui/material';
```

**Why this is risky:** The evidence shows that some projects use a framework transformation to map this syntax to a tree-shaking-friendly form. Do not assume either a payload regression or an optimization without checking the production output.

### Using barrel imports without checking available component entry points

```javascript
import { Stack } from '@mui/material';
```

**Why this is risky:** The evidence PRs recommend the component entry-point form for MUI imports:

```javascript
import Stack from '@mui/material/Stack';
```

Whether this changes the emitted bundle depends on the project’s build configuration and production build output.

## Validation

- Build the production artifact.
- Compare the relevant emitted JavaScript before and after the import change.
- Verify the affected MUI components render and behave as expected.
- If the project uses an import-rewrite transform, confirm that it is active in the production build.