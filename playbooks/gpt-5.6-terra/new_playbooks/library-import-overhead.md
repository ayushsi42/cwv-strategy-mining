---
issue_type: library-import-overhead
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- Availity/availity-react#829
- ukraine-taskforce/requests-frontend#54
- kiva/ui#3788
- twilio-labs/paste#2419
- open-condo-software/condo#1910
- opengovsg/design-system#101
- rudderlabs/rudder-sdk-js#708
- NDLANO/frontend-packages#1415
- jaegertracing/jaeger-ui#1226
- perses/perses#1238
- prevwong/craft.js#540
- tu-graz-library/react-records-marc21#24
- hyperdxio/hyperdx#38
- skbkontur/cassandra-distributed-task-queue#38
- gitpod-io/gitpod#19677
- gohypergiant/standard-toolkit#82
---
# Library import overhead

## What this addresses

Package-root utility imports can cause a browser bundle to include more JavaScript than the functions used by the page. Evidence PRs replace lodash root or named imports with function-level subpath imports such as `lodash/debounce`, `lodash/isEqual`, and `lodash/cloneDeepWith`. Some PRs report smaller bundles after this change.

## When to apply / when to skip
**Apply when:**
- Bundle analysis identifies a package-root utility import, such as `lodash`, as contributing unnecessary code to a browser route.
- The code uses a small, statically known set of utilities with supported function-level or subpath entry points.
- The production browser asset is smaller after the change.

**Skip when:**
- The root import is already proven to tree-shake to equivalent production output.
- Bundle attribution is unavailable, or the utility is not shipped to the affected browser route.

## Recommended approaches

### Use a function-level import

Use the package's supported utility module rather than importing the package namespace or root entry point when bundle analysis shows that the subpath import reduces shipped code.

```javascript
// src/client/search/filter-results.js
import isEqual from 'lodash/isEqual';

export function filtersChanged(previousFilters, nextFilters) {
  return !isEqual(previousFilters, nextFilters);
}
```

Other evidence-backed examples include:

```javascript
import debounce from 'lodash/debounce';
import cloneDeepWith from 'lodash/cloneDeepWith';
import merge from 'lodash/merge';
```

Verify that the application's production browser build resolves the subpath correctly and compare the emitted bundle with the equivalent root import.

## Anti-patterns

### Package-root named import for one utility

```javascript
// Bad — may retain more lodash code than a function-level import
import { debounce } from 'lodash';

searchInput.addEventListener('input', debounce(runSearch, 150));
```

**Why this is bad:** Evidence PRs changed named lodash imports to function-level imports, and bundle-analysis reports in the evidence indicate that root imports can retain unnecessary lodash code. Confirm the production-bundle result before changing an import.

### Package namespace import for a single method

```javascript
// Bad — imports the package root to call one method
import _ from 'lodash';

const nextTopics = _.cloneDeepWith(topics, remapTopicProps);
```

**Why this is bad:** Evidence PRs replaced namespace imports such as `import _ from 'lodash'` with function-level entry points such as `lodash/cloneDeepWith`. Use a supported function-level entry point when production bundle analysis shows that the root import is retained.

## Flavor-specific notes

### Headless

Apply this only to code included in the browser-rendered application bundle. Do not change imports that execute exclusively in server-side content integration or build-time tooling unless the relevant bundle analysis identifies them as browser-shipped overhead.