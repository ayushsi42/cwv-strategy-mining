---
issue_type: javascript-payload-bloat
applicable_flavors:
- eds
- cs
- headless
risk_tier: high
required_validation: []
forbidden_techniques: []
source_prs:
- Adslot/adslot-ui#1349
- apertureless/vue-chartjs#754
- facebook/docusaurus#7085
- epicmaxco/epic-spinners#48
- growthbook/growthbook#1089
- PrairieLearn/PrairieLearn#7958
- ubie-oss/ubie-ui#5
- open-wc/open-wc#2770
- dscvr-one/link-preview-js#2
- digitalfabrik/integreat-app#2776
- Jonghakseo/chrome-extension-boilerplate-react-vite#711
- camunda/feel-builtins#1
- vertex-protocol/vertex-typescript-sdk#320
---
# JavaScript payload bloat

> **Risk tier:** high · **Applies to:** EDS, CS, headless

## What this addresses

The `sideEffects` package metadata convention tells compatible bundlers whether importing a package has side effects. When a package is correctly marked as side-effect-free, a bundler can remove an unused package import from the bundle.

This is recommendation-only: declaring a package side-effect-free incorrectly can remove required CSS imports or other required import-time behavior.

## When to apply / when to skip
**Apply when:**
- A production bundle analysis attributes JavaScript to a package whose exports are only partially used.
- The affected build uses a bundler that honors `sideEffects` metadata.
- Package entry points have been audited for CSS imports and other required import-time behavior.
- A production bundle-size baseline and a consumer import graph are available for comparison.

**Skip when:**
- The package performs required import-time behavior that has not been explicitly preserved.
- The bundle attribution identifies application code rather than a separately auditable package.
- The proposed change is only adding `"sideEffects": false` without establishing that the package has no required import-time behavior.

## Recommended approaches

### Audit package side effects before declaring tree-shakeability

Only mark a package as side-effect-free after auditing its import-time behavior. Preserve known side-effectful files with an explicit allow-list rather than using a blanket `false` declaration.

```text
// Good — EDS block module: blocks/product-card/product-card.js
export default async function decorate(block) {
  await import('./register-elements.js');

  const card = document.createElement('product-card');
  card.textContent = block.textContent;
  block.replaceChildren(card);
}

<!-- Good — CS clientlib: clientlib-product-card/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.product-card]"
    allowProxy="{Boolean}true"/>

# Good — CS clientlib: clientlib-product-card/js.txt
register-elements.js
product-card.js

# Good — CS clientlib: clientlib-product-card/css.txt
styles/product-card.css

// Good — headless browser entry: src/product-card-entry.js
import './styles/product-card.css';
import './register-elements.js';
import { createProductCard } from './product-card.js';

createProductCard(document.querySelector('[data-product-card]'));
```

An explicit list of required CSS and registration files preserves import-time behavior while allowing unused application code to be excluded from the relevant page or entry point.

### Use narrow imports in block code

Keep a block's dependency surface explicit.

```text
// Good — EDS block module: blocks/product-card/product-card.js
export default async function decorate(block) {
  const { formatPrice } = await import('./product-utils.js');
  const price = block.querySelector('[data-price]');

  if (price) {
    price.textContent = formatPrice(price.textContent);
  }
}

<!-- Good — CS clientlib: clientlib-product-card/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.product-card]"
    allowProxy="{Boolean}true"/>

# Good — CS clientlib: clientlib-product-card/js.txt
product-utils.js
product-card.js

// Good — CS clientlib: clientlib-product-card/product-card.js
(function () {
  document.querySelectorAll('[data-product-card]').forEach((card) => {
    const price = card.querySelector('[data-price]');

    if (price) {
      price.textContent = window.siteProductUtils.formatPrice(price.textContent);
    }
  });
}());

// Good — headless browser module: src/product-card.js
import { formatPrice } from './product-utils.js';

document.querySelectorAll('[data-product-card]').forEach((card) => {
  const price = card.querySelector('[data-price]');

  if (price) {
    price.textContent = formatPrice(price.textContent);
  }
});
```

A named import or explicitly listed clientlib source makes the intended dependency explicit.

### Verify retained output with a production consumer

Build a minimal production consumer that imports only the intended package export, then inspect the emitted bundle and exercise required import-time behavior.

```text
// Good — EDS block module: blocks/product-filter/product-filter.js
export default async function decorate(block) {
  const { createProductFilter } = await import('./product-filter.js');
  const filter = createProductFilter(block.querySelector('[data-product-filter]'));

  filter.bind();
}

<!-- Good — CS clientlib: clientlib-product-filter/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.product-filter]"
    allowProxy="{Boolean}true"/>

# Good — CS clientlib: clientlib-product-filter/js.txt
product-filter.js
product-filter-init.js

// Good — CS clientlib: clientlib-product-filter/product-filter-init.js
(function () {
  const element = document.querySelector('[data-product-filter]');

  if (element) {
    window.siteProductFilter.createProductFilter(element).bind();
  }
}());

// Good — headless browser entry: src/product-filter-entry.js
import { createProductFilter } from './product-filter.js';

const filter = createProductFilter(
  document.querySelector('[data-product-filter]'),
);

filter.bind();
```

Check both that unused exports are absent from the production output and that required CSS or other import-time behavior remains present.

## Anti-patterns

### Blanket `sideEffects: false` on a package that imports CSS or registers elements

```text
// Bad — EDS block module: blocks/product-card/product-card.js
export default function decorate(block) {
  const card = document.createElement('product-card');
  card.textContent = block.textContent;
  block.replaceChildren(card);
}

// register-elements.js exists but is never imported by the block.

<!-- Bad — CS clientlib: clientlib-product-card/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.product-card]"
    allowProxy="{Boolean}true"/>

# Bad — CS clientlib: clientlib-product-card/js.txt
product-card.js

# Bad — CS clientlib: clientlib-product-card/css.txt
# styles/product-card.css is omitted and register-elements.js is omitted.

// Bad — headless browser entry: src/product-card-entry.js
import { createProductCard } from './product-card.js';

createProductCard(document.querySelector('[data-product-card]'));

// Required CSS and custom-element registration are omitted.
```

**Why this is bad:** the package imports CSS and registration code for import-time behavior. Declaring all files side-effect-free can allow a bundler to remove files that must be retained.

### Importing a package only for hidden initialization

```text
// Bad — EDS block module: blocks/product-card/product-card.js
export default async function decorate(block) {
  await import('./product-utils.js');
  block.classList.add('is-ready');
}

// Bad — CS clientlib: clientlib-product-card/js.txt
product-utils.js
product-card.js

// Bad — CS clientlib: clientlib-product-card/product-card.js
(function () {
  document.querySelectorAll('[data-product-card]').forEach((block) => {
    block.classList.add('is-ready');
  });
}());

// product-utils.js performs hidden initialization without an explicit API call.

// Bad — headless browser entry: src/product-card-entry.js
import './product-utils.js';

document
  .querySelector('[data-product-card]')
  ?.classList.add('is-ready');
```

**Why this is bad:** the implicit import makes the import-time behavior less explicit and should be audited before changing tree-shaking metadata.

### Shipping a broad utility dependency for a small local operation

```text
// Bad — EDS block module: blocks/image-compare/image-compare.js
export default async function decorate(block) {
  const { isEqual } = await import('./image-utils.js');

  block.dataset.sameImage = String(
    isEqual(block.dataset.firstImage, block.dataset.secondImage),
  );
}

<!-- Bad — CS clientlib: clientlib-image-compare/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.image-compare]"
    allowProxy="{Boolean}true"/>

# Bad — CS clientlib: clientlib-image-compare/js.txt
image-utils.js
image-compare.js

// Bad — CS clientlib: clientlib-image-compare/image-compare.js
(function () {
  document.querySelectorAll('[data-first-image][data-second-image]').forEach((element) => {
    element.dataset.sameImage = String(
      window.siteImageUtils.isEqual(
        element.dataset.firstImage,
        element.dataset.secondImage,
      ),
    );
  });
}());

// Bad — headless browser module: src/image-compare.js
import { isEqual } from './image-utils.js';

export function hasSameImage(first, second) {
  return isEqual(first, second);
}
```

Use this pattern only after bundle analysis confirms that the dependency's retained cost is justified by the required behavior.

## Flavor-specific notes

### EDS

Audit packages imported by block modules and verify the production output for the relevant page or entry point.

Do not replace a required registration import with dynamic loading solely to reduce bundle size without verifying required ordering.

### CS

Audit the build path that produces browser assets and confirm whether it honors `sideEffects` metadata before relying on package tree shaking.

### Headless

Audit browser-rendered application entry points and their package imports. Preserve required CSS imports and other import-time behavior in explicit entries or a package `sideEffects` allow-list before enabling tree shaking.