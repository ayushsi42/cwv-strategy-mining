### Remove retired feature-flag branches and orphaned imports

After a feature flag is permanently retired, remove the obsolete branch, its implementation, and any imports and tests that only supported that branch.

```javascript
// Good — blocks/logs/logs.js
import { getMetadata } from '../../scripts/aem.js';

export default async function decorate(block) {
  if (getMetadata('logs-enabled') !== 'true') {
    block.remove();
    return;
  }

  const { decorateLogsTable } = await import('./logs-table.js');
  await decorateLogsTable(block);
}
```

### Leaving retired branches in place after selecting the new default

```javascript
// Bad — blocks/logs/logs.js
import { getMetadata } from '../../scripts/aem.js';

export default async function decorate(block) {
  if (getMetadata('logs-enabled') !== 'true') {
    block.remove();
    return;
  }

  if (getMetadata('logs-infinite-scroll') === 'true') {
    const { decorateInfiniteLogs } = await import('./infinite-logs.js');
    await decorateInfiniteLogs(block);
  } else {
    const { decorateLogsTable } = await import('./logs-table.js');
    await decorateLogsTable(block);
  }
}
```

**Why this is bad:** Keeping both paths retains code and imports that might otherwise be removed. Removing obsolete code has reduced bundle size in the cited PRs, although tree-shaking does not always eliminate unused code.

> **Source PRs** — **approach:** getsentry/sentry#98296, OneSignal/OneSignal-Website-SDK#1372, Automattic/wp-calypso#108174, OpenNews/srccon-site-starterkit#1, SAP/fundamental-ngx#7407 · **anti-pattern:** getsentry/sentry#83982, SolidInvoice/SolidInvoice#1551, aarcangeli/ue-web-viewer#8, home-assistant/frontend#18793