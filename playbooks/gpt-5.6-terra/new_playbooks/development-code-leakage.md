---
issue_type: development-code-leakage
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- salesforce/lwc#3231
- framer/motion#1864
- shuding/nextra#1268
- netlify/edge-bundler#519
- iTwin/iTwinUI#2131
---
# Development code leakage

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless

## What this addresses

Production browser bundles can retain development-only warnings, validation maps, hot-reload helpers, and diagnostic code when environment checks are not replaced with static values during the build. Removing unreachable development branches can reduce JavaScript bundle size.

## When to apply / when to skip
**Apply when:**
- A production bundle contains development warning strings, `module.hot`, diagnostic helpers, or development-only validation data.
- Source code uses `process.env.NODE_ENV` or an equivalent environment condition and the production build can replace it statically.
- The build output and package export conditions are known for the affected client-side module.
- The affected code is shipped to browsers through an EDS block, AEM clientlib, or headless application bundle.

**Do not apply when:**
- The environment condition is evaluated dynamically in the browser and no build-time replacement mechanism is configured.
- The candidate module is also executed server-side and changing its environment condition could alter publish runtime behavior.
- The build selects package export conditions differently between local development, CI, and production deployment.
- Production bundle inspection shows that the development branch and its dependencies are already absent.

## Recommended approaches

### Use a direct build-time production guard in compiled browser code

Keep the environment expression directly in the branch that owns the development-only behavior. A production build can replace `process.env.NODE_ENV` with a string literal and eliminate an unreachable branch containing warning calls.

```javascript
// Good — CS/AMS clientlib source compiled before packaging
(function () {
  function validateHero(image) {
    if (process.env.NODE_ENV !== 'production' && !image) {
      console.warn('Hero component requires an image.');
    }
  }

  window.site = window.site || {};
  window.site.validateHero = validateHero;
}());
```

```javascript
// Good — EDS block artifact deployed after development diagnostics are removed
export default function decorate(block) {
  const image = block.querySelector('img');

  if (!image) {
    block.classList.add('hero--missing-image');
  }
}
```

```javascript
// Good — expected CS/AMS production clientlib output after static replacement
(function () {
  window.site = window.site || {};
  window.site.validateHero = function validateHero() {
    // Development-only warning removed.
  };
}());
```

The environment value must be substituted before minification so the minifier sees a statically unreachable branch rather than shipping a browser-time condition.

### Keep EDS block browser code free of runtime environment globals

EDS block code executes in the browser and should not depend on a Node.js-style `process` global unless a verified site build replaces it before deployment. Keep production block behavior self-contained, and run authoring or development diagnostics in build-time tooling or development-only artifacts.

```javascript
// Good — blocks/hero/hero.js
export default function decorate(block) {
  const image = block.querySelector('img');

  if (!image) {
    block.classList.add('hero--missing-image');
    return;
  }

  image.loading = 'eager';
}
```

If development diagnostics are required for an EDS block, verify that the deployed browser artifact has removed both the diagnostic code and any environment-global reference.

### Keep development-only clientlib diagnostics out of the production category

For CS and AMS, keep the publish clientlib category limited to production-safe code. The clientlib should package a production-ready JavaScript artifact rather than source that expects a browser `process` global.

```xml
<!-- Good — jcr_root/apps/site/clientlibs/site-base/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.base]"
          dependencies="[site.core]"/>
```

```html
<!-- Good — jcr_root/apps/site/components/page/page.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='site.base'}"></sly>
```

```javascript
// Good — jcr_root/apps/site/clientlibs/site-base/js/navigation.js
(function () {
  function decorateNavigation(block) {
    block.classList.add('is-decorated');
  }

  window.site = window.site || {};
  window.site.decorateNavigation = decorateNavigation;
}());
```

Verify that the JavaScript stored in the clientlib does not retain development warning text or `process.env.NODE_ENV`.

### Select production package exports for browser dependencies

When a dependency provides separate development and production entry points, ensure the production browser build resolves the production export and reserves the `development` condition for development builds.

```text
# Good — production artifacts selected for browser delivery

blocks/navigation/navigation.js
apps/site/clientlibs/site-base/js/navigation.js
dist/prod/navigation.js
```

```javascript
// Good — EDS production block entrypoint: blocks/navigation/navigation.js
export default function decorate(block) {
  block.classList.add('is-decorated');
}
```

```javascript
// Good — CS/AMS production clientlib entrypoint:
// apps/site/clientlibs/site-base/js/navigation.js
(function () {
  window.site = window.site || {};
  window.site.decorateNavigation = function decorateNavigation(block) {
    block.classList.add('is-decorated');
  };
}());
```

This allows the production entrypoint to omit development-only warnings and diagnostics.

## Anti-patterns

### Guarding a module-scoped development helper only at the call site

```javascript
// Bad — EDS block code with a browser-time development condition
const attributeWarningMap = {
  className: 'Use class instead of className in authored HTML.',
  tabIndex: 'Check tab order before publishing.',
  title: 'Title should match the component label.',
};

function warnForAttribute(name) {
  console.warn(attributeWarningMap[name]);
}

const isDevelopment = new URLSearchParams(window.location.search).has('debug');

export default function decorate(block) {
  const attributeName = block.dataset.attributeName;

  if (isDevelopment && attributeName) {
    warnForAttribute(attributeName);
  }
}
```

```javascript
// Bad — CS/AMS clientlib JavaScript
(function () {
  const attributeWarningMap = {
    className: 'Use class instead of className in authored HTML.',
    tabIndex: 'Check tab order before publishing.',
    title: 'Title should match the component label.',
  };

  function warnForAttribute(name) {
    console.warn(attributeWarningMap[name]);
  }

  window.site = window.site || {};
  window.site.validateAttribute = function validateAttribute(name) {
    if (process.env.NODE_ENV !== 'production') {
      warnForAttribute(name);
    }
  };
}());
```

**Why this is bad:** the module-scoped warning map and helper can remain in the production bundle when the build cannot prove that their initialization is removable, even if the warning call is removed.

### Using a browser-time environment fallback

```javascript
// Bad — EDS block code
const isDevelopment =
  typeof process !== 'undefined' &&
  process.env &&
  process.env.NODE_ENV !== 'production';

export default function decorate(block) {
  if (isDevelopment) {
    console.warn('Navigation block is running in development mode.');
  }

  block.classList.add('is-decorated');
}
```

**Why this is bad:** browser-time checks can prevent static elimination and can leave `process` references and development warning code in the production artifact.

### Shipping a development package entrypoint in the publish bundle

```javascript
// Bad — EDS development block entrypoint
export default function decorate(block) {
  console.warn(
    'Search block diagnostics: verify authored filters and result configuration.'
  );

  block.classList.add('is-decorated');
}
```

```javascript
// Bad — CS/AMS development clientlib entrypoint
(function () {
  window.site = window.site || {};
  window.site.decorateSearch = function decorateSearch(block) {
    console.warn(
      'Search block diagnostics: verify authored filters and result configuration.'
    );

    block.classList.add('is-decorated');
  };
}());
```

**Why this is bad:** selecting a development export for publish ships diagnostics and validation work instead of allowing the production entrypoint to omit it.

## Flavor-specific notes

### EDS

Check the block source and the browser artifact independently. Do not assume a Node.js environment global is available at runtime.

Do not add a `typeof process !== 'undefined'` fallback to make block source run in browsers. If an EDS delivery process transforms source files, verify that it replaces environment expressions before deployment and that the emitted artifact contains neither `process.env.NODE_ENV` nor removed warning text.

### CS / AMS

Before changing code, trace the clientlib category from its `.content.xml` definition through the page component's HTL inclusion. Confirm that its production artifact is used on publish pages and that authoring-only diagnostics are not shared with visitor-facing categories.

For AMS, if JavaScript is prebuilt outside Maven before clientlib packaging, verify that the build output—not only the source—replaces environment expressions before the artifact is copied to publish.

### Headless

Apply this to the browser application or hydration bundle that consumes AEM content, not to AEM content APIs themselves. Confirm that the deployment build selects production package exports and statically replaces environment checks before JavaScript is served to clients.