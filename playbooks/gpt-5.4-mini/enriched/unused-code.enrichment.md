### Tree-shake icon imports to individual modules

When a library ships many icons but a page uses only a few, import each icon from its own module instead of the package root. This can let the bundler include only the icons actually referenced, instead of pulling in the full icon set.

```javascript
import CheckCircle from './icons/CheckCircle.js';
import Info from './icons/Info.js';
import WarningCircle from './icons/WarningCircle.js';
import X from './icons/X.js';

import { createElement } from './utils.js';

export function Alert() {
  return createElement('span', { class: 'icon icon--check-circle', 'aria-hidden': 'true' });
}
```

## Anti-patterns

### Importing the full icon package when only a few icons are used

```javascript
// Bad
import CheckCircle from './icons/index.js';
import Info from './icons/index.js';
import WarningCircle from './icons/index.js';
import X from './icons/index.js';

import { createElement } from './utils.js';

export function Alert() {
  return createElement('span', { class: 'icon icon--check-circle', 'aria-hidden': 'true' });
}
```

**Why this is bad:** Importing from a shared module that re-exports the full icon set can pull in more icon code than the page needs, which can increase bundle size.

> **Source PRs** — **approach:** datahub-project/datahub#16338, datahub-project/datahub#16615, getsentry/sentry#98296, ecoacoustics/web-components#513, Automattic/wp-calypso#108174 · **anti-pattern:** nader-eloshaiker/screen-geometry-app#479, SolidInvoice/SolidInvoice#1551, galacticcouncil/hydration-ui#3622, expo/expo#24314