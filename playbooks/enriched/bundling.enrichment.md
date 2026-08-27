### Split oversized icon catalogs into standalone imports

When a feature needs only a few icons from a large catalog, import the specific icon modules directly instead of pulling in the full package root. Keep any icon picker or catalog UI separate from the runtime component path so unused icons can be excluded from the page payload.

**Good example:**

```javascript
import CheckCircle from '@phosphor-icons/react/dist/icons/CheckCircle.js';
import Info from '@phosphor-icons/react/dist/icons/Info.js';
import WarningCircle from '@phosphor-icons/react/dist/icons/WarningCircle.js';
import X from '@phosphor-icons/react/dist/icons/X.js';

import { AlertIconWrapper } from './components/AlertIconWrapper.js';

export function AlertIcon({ variant }) {
  const icon =
    variant === 'success' ? CheckCircle :
    variant === 'info' ? Info :
    variant === 'warning' ? WarningCircle :
    X;

  return AlertIconWrapper({ icon });
}
```

**Bad example:**

```javascript
import * as Icons from '@phosphor-icons/react';
import React from 'react';

export function AlertIcon({ variant }) {
  const icon =
    variant === 'success' ? Icons.CheckCircle :
    variant === 'info' ? Icons.Info :
    variant === 'warning' ? Icons.WarningCircle :
    Icons.X;

  return <AlertIconWrapper icon={icon} />;
}
```

**Why this is bad:**
- Importing from the package root can pull in far more code than the feature needs.
- It can increase the initial bundle size and parse/execute cost on every page that uses the component.
- It can make it harder for the bundler to drop unused icons, especially when the catalog is referenced as a namespace object.

> **Source PRs** — **approach:** ant-design/x#1402, datahub-project/datahub#16338, sam-goodwin/itty-aws#62, vlossom-ui/vlossom#117, getsentry/sentry#98296 · **anti-pattern:** n8n-io/n8n#25649, getsentry/sentry#85592, getsentry/gib-potato#275, graphcommerce-org/graphcommerce#1909