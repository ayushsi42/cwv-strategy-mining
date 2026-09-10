---
issue_type: excess-javascript-payload
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- aws-amplify/amplify-ui#1569
- Orfium/orfium-ictinus#567
- verlok/vanilla-lazyload#607
- OfficeDev/microsoft-teams-library-js#2513
---
# Excess JavaScript payload

> **Risk tier:** medium · **Applies to:** EDS, CS, headless

## What this addresses

A package that exposes only a bundled entry point can include code that consumers do not use. Publishing an ESM build and exposing it through package metadata can allow bundlers to remove unused exports from the final bundle.

## When to apply / when to skip
**Apply when:**
- Bundle analysis identifies an internal or third-party package as contributing unused exports or modules to the initial JavaScript payload.
- The consuming application resolves ESM package entry points and its production build supports tree-shaking.
- A package build currently produces a single non-tree-shakeable output.

**Skip when:**
- The identified JavaScript is application code rather than a reusable package with package entry points to correct.
- The consumer cannot resolve ESM package exports.
- The payload is dominated by code that the page actually uses.

## Recommended approaches

### Publish preserved ESM modules and map package exports

Build the package as preserved ESM modules instead of flattening all source modules into one ESM file, then expose the ESM entry point through package metadata.

```xml
<!-- CS: ui.apps/src/main/content/jcr_root/apps/site/clientlibs/product-search/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.product-search]"
    dependencies="[site.product-search.filters]"
    allowProxy="{Boolean}true"/>
```

```javascript
// EDS: blocks/product-search/product-search.js
export default async function decorate(block) {
  const { decorateSearch } = await import('./search.js');
  decorateSearch(block);
}

// CS: clientlibs/product-search/js/product-search.js
(function () {
  document.querySelectorAll('.product-search').forEach((block) => {
    block.classList.add('product-search-ready');
  });
}());

// Headless: src/product-search.js
export async function decorateProductSearch(block) {
  const { decorateSearch } = await import('./search.js');
  decorateSearch(block);
}
```

```javascript
// EDS: blocks/product-search/search.js
export function decorateSearch(block) {
  block.classList.add('product-search-ready');
}

// CS: clientlibs/product-search/js/search.js
(function (window) {
  window.SiteProductSearch = window.SiteProductSearch || {};
  window.SiteProductSearch.decorateSearch = function decorateSearch(block) {
    block.classList.add('product-search-ready');
  };
}(window));

// Headless: src/search.js
export function decorateSearch(block) {
  block.classList.add('product-search-ready');
}
```

```javascript
// Keep feature code in separate source files rather than concatenating it
// into one generated application file.

// EDS: blocks/product-search/product-search.js
export default async function decorate(block) {
  const { decorateSearch } = await import('./search.js');
  decorateSearch(block);
}

// CS: clientlibs/product-search/js.txt
search.js
product-search.js

// Headless: src/product-search.js
export async function decorateProductSearch(block) {
  const { decorateSearch } = await import('./search.js');
  decorateSearch(block);
}
```

Preserved ESM retains static import/export relationships for consumer bundlers. Configure consumers to resolve the ESM `import` or `module` entry rather than a bundled CommonJS or UMD entry.

### Declare side effects deliberately

Packages can declare `"sideEffects": false` when their modules are intended to be treated as side-effect-free by bundlers.

```xml
<!-- CS: keep required initialization code in its own client library dependency. -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.commerce-widgets]"
    dependencies="[site.commerce-widgets.registration]"
    allowProxy="{Boolean}true"/>
```

Use this declaration only when it matches the package's actual import behavior.

### Consume named ESM exports

Import the package capability needed by the block or component.

```javascript
// EDS: blocks/product-search/product-search.js
export default async function decorate(block) {
  const { decorateSearch } = await import('./search.js');
  decorateSearch(block);
}

// CS: clientlibs/product-search/js/product-search.js
(function (window, document) {
  const decorateSearch = window.SiteProductSearch.decorateSearch;

  document.querySelectorAll('.product-search').forEach((block) => {
    decorateSearch(block);
  });
}(window, document));

// Headless: src/product-search.js
export async function decorateProductSearch(block) {
  const { decorateSearch } = await import('./search.js');
  decorateSearch(block);
}
```

Named imports can be used with a tree-shakeable ESM package so consumer bundlers can identify the exports in use.

## Anti-patterns

### Shipping one flattened ESM bundle as the package module entry

```xml
<!-- Bad: one client library contains every feature rather than using focused categories. -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.library]"
    allowProxy="{Boolean}true"/>
```

```javascript
// Bad — EDS: blocks/product-search/product-search.js loads every feature.
export default async function decorate(block) {
  const widgets = await import('./all-widgets.js');

  widgets.initializeAllWidgets(document);
  widgets.decorateSearch(block);
}

// Bad — CS: clientlibs/library/js/all-widgets.js contains every feature.
(function (window, document) {
  window.SiteLibrary = {
    decorateSearch(block) {
      block.classList.add('product-search-ready');
    },
    createFilterState() {},
    createRecommendations() {},
    startAnalytics() {},
    initializeAllWidgets() {
      document.querySelectorAll('.product-search').forEach((block) => {
        this.decorateSearch(block);
      });
    },
  };
}(window, document));

// Bad — Headless: src/all-widgets.js exports every feature together.
export function decorateSearch(block) {
  block.classList.add('product-search-ready');
}
export function createFilterState() {}
export function createRecommendations() {}
export function startAnalytics() {}
```

**Why this is bad:** A single bundled ESM output may be less tree-shakeable than a preserved-module ESM build.

### Marking all files side-effect-free without validating package behavior

```xml
<!-- Bad: required registration code is not declared as a dependency. -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.commerce-widgets]"
    allowProxy="{Boolean}true"/>
```

```javascript
// Bad — EDS: blocks/commerce-widget/commerce-widget.js
export default async function decorate(block) {
  const { decorateWidget } = await import('./widget.js');
  decorateWidget(block);
}

// register-elements.js is required but never loaded:
// customElements.define('commerce-widget', CommerceWidget);

// Bad — CS: registration.js is required but omitted from js.txt.
(function () {
  customElements.define('commerce-widget', class CommerceWidget extends HTMLElement {});
}());
```

**Why this is bad:** An inaccurate `sideEffects` declaration can cause bundlers to treat modules as removable when they should be retained.

### Importing the full package for one feature

```javascript
// Bad — EDS: blocks/product-search/product-search.js
export default async function decorate(block) {
  const commerceWidgets = await import('./commerce-widgets.js');

  commerceWidgets.initializeAllWidgets(document);
  commerceWidgets.decorateSearch(block);
}

// Bad — CS: clientlibs/product-search/js/product-search.js
(function (window, document) {
  const commerceWidgets = window.SiteCommerceWidgets;

  commerceWidgets.initializeAllWidgets(document);
  document.querySelectorAll('.product-search').forEach((block) => {
    commerceWidgets.decorateSearch(block);
  });
}(window, document));

// Bad — Headless: src/product-search.js
export async function decorateProductSearch(block) {
  const commerceWidgets = await import('./commerce-widgets.js');

  commerceWidgets.initializeAllWidgets(document);
  commerceWidgets.decorateSearch(block);
}
```

**Why this is bad:** Prefer named imports when consuming a tree-shakeable package so the consumer build can identify the capability being used.

## Flavor-specific notes

### EDS

Ensure the EDS build resolves the package's ESM `import` export rather than a bundled `main` or browser entry.

### CS

Tree-shaking depends on the frontend build consuming the package. Confirm that the build producing the client-side asset resolves the package's ESM entry.

### Headless

Apply this to the frontend application package consumed by the headless renderer. Verify that the deployed production build resolves ESM exports rather than a full CommonJS or UMD entry point.