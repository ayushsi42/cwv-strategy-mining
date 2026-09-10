---
issue_type: library-import-bloat
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: low
required_validation: []
forbidden_techniques: []
source_prs:
- woowacourse/javascript-lotto#152
- regen-network/regen-web#1180
- 4ian/GDevelop#4328
- dataiku/solutions-contrib#47
- MetaMask/metamask-extension#20363
---
# Library import bloat

> **Risk tier:** low · **Applies to:** EDS, CS, AMS, Headless

## What this addresses

Importing the aggregate Lodash package can increase browser bundle size when a page needs only a small number of utilities. Replacing an aggregate import with an equivalent Lodash method module can reduce bundle size.

One reported change reduced a bundle from 114 KB to 44 KB when importing only `shuffle`.

## When to apply / when to skip
**Apply when:**
- The audited browser bundle contains Lodash and source attribution identifies an aggregate import such as `import _ from 'lodash'` or `import { shuffle } from 'lodash'`.
- The file uses one or a small, statically identifiable set of Lodash methods.
- The installed Lodash version provides the corresponding method module, such as `lodash/shuffle`.
- The import is part of client-side code delivered to the browser, not a server-only Sling Model or build-time script.
- For CS or AMS clientlibs, the existing frontend pipeline already resolves method-level Lodash paths.

**Skip when:**
- The file intentionally uses a broad, dynamic Lodash API such as `_[methodName](value)`.
- The import is from a project-specific wrapper whose public API must remain aggregate.
- The package manager resolves Lodash through an alias or custom vendor bundle that cannot safely resolve method-level paths.
- The identified Lodash code is not included in the audited page's client bundle.
- Replacing the Lodash method would change required edge-case behavior that the component depends on.

## Recommended approaches

### Import the required Lodash method directly

For browser applications with an existing module-aware build process, replace an aggregate Lodash import with a method-level module.

```javascript
// EDS — blocks/featured-projects/featured-projects.js
// lodash-shuffle.js is a vendored method module in this block directory.
import shuffle from './lodash-shuffle.js';

export default function decorate(block) {
  const cards = [...block.querySelectorAll(':scope > div')];
  const featuredCards = shuffle(cards).slice(0, 3);

  block.replaceChildren(...featuredCards);
}

// CS / AMS —
// /apps/project/clientlibs/featured-projects/.content.xml
//
// <jcr:root
//   xmlns:jcr="http://www.jcp.org/jcr/1.0"
//   jcr:primaryType="cq:ClientLibraryFolder"
//   categories="[project.featured-projects]"
//   dependencies="[project.vendor.lodash.shuffle]"/>
//
// /apps/project/clientlibs/featured-projects/js/featured-projects.js
(function () {
  function decorateFeaturedProjects(block) {
    const cards = [...block.querySelectorAll(':scope > div')];
    const featuredCards = window.lodashShuffle(cards).slice(0, 3);

    block.replaceChildren(...featuredCards);
  }

  document.querySelectorAll('[data-featured-projects]').forEach(decorateFeaturedProjects);
}());

// Headless browser application — vendor/lodash-shuffle.js is included in the application bundle.
import shuffleForHeadless from './vendor/lodash-shuffle.js';

export function selectFeaturedCards(cards) {
  return shuffleForHeadless(cards).slice(0, 3);
}
```

A method-level import makes the required utility explicit and can reduce bundle size compared with importing the aggregate Lodash entry point.

## Anti-patterns

### Aggregate default import for one utility

```javascript
// EDS — blocks/featured-projects/featured-projects.js
// lodash.js is a vendored aggregate Lodash build in this block directory.
import _ from './lodash.js';

export default function decorate(block) {
  const cards = [...block.querySelectorAll(':scope > div')];
  block.replaceChildren(..._.shuffle(cards).slice(0, 3));
}

// CS / AMS —
// The component clientlib depends on an aggregate Lodash vendor clientlib.
(function () {
  function decorateFeaturedProjects(block) {
    const cards = [...block.querySelectorAll(':scope > div')];
    block.replaceChildren(...window._.shuffle(cards).slice(0, 3));
  }

  document.querySelectorAll('[data-featured-projects]').forEach(decorateFeaturedProjects);
}());

// Headless browser application — lodash.js is an aggregate vendored browser module.
import lodash from './vendor/lodash.js';

export function selectFeaturedCards(cards) {
  return lodash.shuffle(cards).slice(0, 3);
}
```

**Why this is bad:** The source imports the aggregate Lodash entry point even though the block uses only `shuffle`. Importing the whole library can increase bundle size; a method-level import makes the required dependency explicit.

### Named import from the aggregate package without verifying output

```javascript
// EDS — blocks/product-list/product-list.js
// lodash.js is a vendored aggregate Lodash build in this block directory.
import { shuffle } from './lodash.js';

export default function decorate(block) {
  const items = [...block.querySelectorAll(':scope > div')];
  const randomizedItems = shuffle(items);

  block.replaceChildren(...randomizedItems);
}

// CS / AMS — aggregate Lodash is supplied by a dependent vendor clientlib.
(function () {
  const items = [...document.querySelectorAll('[data-product-list] > div')];
  const randomizedItems = window._.shuffle(items);

  document.querySelector('[data-product-list]')?.replaceChildren(...randomizedItems);
}());

// Headless browser application — aggregate vendored module.
import { shuffle as shuffleForHeadless } from './vendor/lodash.js';

export function randomizeItems(items) {
  return shuffleForHeadless(items);
}
```

**Why this is bad:** This resolves through the aggregate `lodash` package entry point. It may not be tree-shaken as expected, so verify the emitted browser bundle before treating it as equivalent to a method-level import.

### Namespace import used for a single method

```javascript
// EDS — blocks/featured-projects/featured-projects.js
// lodash.js is a vendored aggregate Lodash build in this block directory.
import * as lodash from './lodash.js';

export default function decorate(block) {
  const cards = [...block.querySelectorAll(':scope > div')];
  const visibleCards = lodash.shuffle(cards).slice(0, 3);

  block.replaceChildren(...visibleCards);
}

// CS / AMS — aggregate Lodash is supplied by a dependent vendor clientlib.
(function () {
  const cards = [...document.querySelectorAll('[data-featured-projects] > div')];
  const visibleCards = window._.shuffle(cards).slice(0, 3);

  document.querySelector('[data-featured-projects]')?.replaceChildren(...visibleCards);
}());

// Headless browser application — aggregate vendored module.
import * as lodashForHeadless from './vendor/lodash.js';

export function selectVisibleCards(cards) {
  return lodashForHeadless.shuffle(cards).slice(0, 3);
}
```

**Why this is bad:** The namespace import expresses a dependency on the aggregate module when the code requires only one method. Importing the aggregate library can increase bundle size.

## Flavor-specific notes

### EDS

Make the change in the block JavaScript file that imports Lodash.

### CS

Confirm whether the project’s existing frontend pipeline resolves `lodash/shuffle` before using a method-level import.

### AMS

Confirm that the deployed clientlib pipeline supports method-level Lodash paths and preserves the current import interop.

### Headless

Apply the change in the browser application or component bundle that renders the AEM-delivered content.