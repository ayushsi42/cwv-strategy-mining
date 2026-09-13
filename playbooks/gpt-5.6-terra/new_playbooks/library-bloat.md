---
issue_type: library-bloat
applicable_flavors:
- eds
- cs
risk_tier: medium
forbidden_techniques: []
flavor_overrides:
  eds: {}
  cs: {}
required_validation: []
source_prs:
- datahub-project/datahub#16615
- wso2/identity-apps#9366
- folio-org/stripes-acq-components#928
- regen-network/regen-web#843
- decidim/decidim#9161
- kelvininc/ui-components#136
- lightdash/lightdash#9323
- navikt/meroppfolging-mikrofrontend#81
- binary-com/deriv-app#16741
- apache/superset#31019
---
# Library bloat

> **Risk tier:** medium · **Applies to:** EDS, CS

## What this addresses

The evidence PRs associate removing Moment.js with reduced bundle size or improved frontend performance in several applications. For example, DataHub replaced Moment.js and Moment Timezone with Day.js and reported an estimated net saving of approximately 318 KB gzipped. Other PRs removed Moment.js dependencies while migrating usage to Day.js or project utilities.

The supplied evidence does not include direct LCP or INP measurements.

## When to apply / when to skip
**Apply when:**
- The audited page or shared client code imports Moment.js, Moment Timezone, or related locale packages.
- An inventory identifies the Moment.js APIs, locales, timezone behavior, and plugins currently used.
- The application already ships Day.js or has project utilities that can replace the required behavior.
- Tests or manual verification cover the affected formatting, parsing, locale, timezone, and date-boundary behavior.
- The migration removes the Moment.js dependency rather than leaving both libraries as required application dependencies.

**Skip when:**
- Required timezone, locale, parsing, or date-boundary behavior has not been identified and verified.
- The existing implementation depends on behavior that is not covered by the proposed replacement.
- The dependency is owned by a third-party package that cannot be changed independently.

## Recommended approaches

### Inventory current usage before replacing Moment.js

Identify imports, dependency declarations, locale imports, timezone usage, and plugins before making a replacement.

The evidence includes migrations with differing requirements:

- DataHub replaced `moment` and `moment-timezone` with Day.js and a shared Day.js utility.
- WSO2 replaced Moment.js locale imports with Day.js locale imports.
- Lightdash added Day.js `duration` and `utc` plugins where those APIs were required.
- Deriv replaced Moment.js usage in its wallets package with project utilities.
- Superset removed `moment`, `moment-timezone`, and `moment-locales-webpack-plugin` as part of its date-picker migration.

### Reuse an existing date utility where the application has one

DataHub imported Day.js through a shared utility in several files, and Deriv replaced Moment.js calls with existing project utilities. Where an application already has a shared date abstraction, use it consistently rather than introducing another date dependency.

```text
EDS: blocks/date/date.js
import { formatDate } from '../../scripts/date-utils.js';

export default function decorate(block) {
  const date = block.querySelector('time');

  if (date?.dateTime) {
    date.textContent = formatDate(date.dateTime, 'YYYY-MM-DD');
  }
}

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/.content.xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
  xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[site.date]"
  dependencies="[site.date-utils]"/>

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/js/date.js
(() => {
  document.querySelectorAll('.date time[datetime]').forEach((date) => {
    date.textContent = window.siteDateUtils.formatDate(
      date.dateTime,
      'YYYY-MM-DD',
    );
  });
})();
```

Verify that the shared utility configures every plugin required by the migrated call sites.

### Remove Moment.js dependencies after migration

After replacing usage, remove Moment.js packages from the relevant dependency manifest and lockfile where applicable. DataHub, WSO2, Superset, Lightdash, Deriv, and FOLIO all removed Moment.js dependencies as part of their migrations.

DataHub also added restricted-import rules to prevent new `moment` and `moment-timezone` imports after removal.

```javascript
// Example enforcement pattern from the evidence.
'no-restricted-imports': [
  'error',
  {
    paths: [
      {
        name: 'moment',
        message: 'moment was removed for bundle size. Use dayjs instead.',
      },
      {
        name: 'moment-timezone',
        message: 'moment-timezone was removed for bundle size. Use dayjs with timezone plugin instead.',
      },
    ],
  },
];
```

### Validate locale, timezone, and duration behavior

Do not assume a migration is complete solely because basic formatting calls compile. The evidence shows migrations that explicitly handled:

- locale imports and locale selection;
- timezone functionality;
- UTC formatting;
- duration calculations; and
- date-range behavior across timezones.

Test the behavior used by the application before removing Moment.js.

## Anti-patterns

### Keeping Moment.js imports after adding Day.js

```text
EDS: blocks/date/date.js
// Bad: both locally served libraries remain required by the block.
import moment from '../../scripts/moment.js';
import dayjs from '../../scripts/dayjs.js';

export default function decorate(block) {
  const date = block.querySelector('time');

  date.textContent = dayjs(date.dateTime).format('MMM D, YYYY');
  block.dataset.month = moment(date.dateTime).format('MM');
}

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/.content.xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
  xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[site.date]"
  dependencies="[site.dayjs,site.moment]"/>

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/js/date.js
// Bad: both clientlib dependencies remain required.
(() => {
  document.querySelectorAll('.date time[datetime]').forEach((date) => {
    date.textContent = window.dayjs(date.dateTime).format('MMM D, YYYY');
    date.closest('.date').dataset.month = window.moment(date.dateTime).format('MM');
  });
})();
```

**Why this is bad:** Moment.js is still imported and used, so this module has not fully migrated away from Moment.js. The evidence PRs that removed Moment.js also removed or replaced its remaining call sites.

### Replacing Moment.js without migrating required plugins or locale behavior

```text
EDS: blocks/date/date.js
// Bad: the local Day.js module has not been configured with the utc plugin.
import dayjs from '../../scripts/dayjs.js';

export default function decorate(block) {
  const date = block.querySelector('time');

  date.textContent = dayjs(date.dateTime).utc().format('YYYY-MM-DD');
}

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/.content.xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
  xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[site.date]"
  dependencies="[site.dayjs]"/>

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/js/date.js
// Bad: site.dayjs does not include the utc plugin.
(() => {
  document.querySelectorAll('.date time[datetime]').forEach((date) => {
    date.textContent = window.dayjs(date.dateTime).utc().format('YYYY-MM-DD');
  });
})();
```

**Why this is bad:** The evidence shows that some migrations required explicit Day.js plugins such as `utc` and `duration`, and some required locale imports. Verify that the replacement supports the APIs and locale behavior used by the original code.

### Adding another date library when the application already has a supported utility

```text
EDS: blocks/date/date.js
// Bad: this block introduces a separate local library instead of the shared utility.
import dayjs from './dayjs.js';

export default function decorate(block) {
  const date = block.querySelector('time');

  date.textContent = dayjs(date.dateTime).format('MMM D, YYYY');
}

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/.content.xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
  xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[site.date]"
  dependencies="[site.dayjs]"/>

CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/clientlib-date/js/date.js
// Bad: this clientlib uses Day.js rather than the existing site.date-utils category.
(() => {
  document.querySelectorAll('.date time[datetime]').forEach((date) => {
    date.textContent = window.dayjs(date.dateTime).format('MMM D, YYYY');
  });
})();
```

**Why this is bad:** DataHub and Deriv demonstrate migrations that reuse shared utilities already available in the application. Introducing a separate local date dependency can make dependency management less consistent.

## Flavor-specific notes

### EDS

No EDS-specific implementation evidence was provided. Before changing shared scripts or block code, inventory all imports and verify the date behavior required by each affected block.

### CS

No CS-specific implementation evidence was provided. Before removing a dependency from shared client code, inventory all consumers and verify locale, timezone, parsing, and date-boundary behavior used by affected components.