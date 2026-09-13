---
issue_type: icon-payload-bloat
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
forbidden_techniques:
- pattern: import\s+\*\s+as\s+\w+\s+from\s+['"][^'"]*(?:[Ii]cons?|[Ss]vg)[^'"]*['"]
  reason: Avoid namespace-importing an icon or SVG registry when icons are accessed
    dynamically; this can retain every icon in the client bundle
- pattern: (?:Object\.keys|keys)\s*\(\s*\w*(?:[Ii]cons?|[Ss]vg)\w*\s*\)\s*\.(?:forEach|map)\s*\(
  reason: Avoid enumerating an icon registry at runtime; this can require the bundle
    to retain every SVG definition
- pattern: \w*(?:[Ii]cons?|[Ss]vg)\w*\s*\[\s*[A-Za-z_$][A-Za-z0-9_$]*\s*\]
  reason: Avoid resolving icons from a runtime-computed registry key when static imports
    or a deliberately small runtime set are possible
flavor_overrides:
  cs:
    extra_validation:
    - clientlib_module_output_verified
    - clientlib_category_scope_known
  headless:
    extra_validation:
    - frontend_build_pipeline_ownership_known
required_validation: []
source_prs:
- Lissy93/dashy#194
- opentripplanner/otp-ui#277
- wellcomecollection/wellcomecollection.org#7050
- antvis/S2#654
- openmrs/openmrs-esm-core#437
- channel-io/bezier-react#802
- bitwarden/clients#3427
- hpcc-systems/Tombolo#502
- justeattakeaway/pie#40
- RedHatInsights/landing-page-frontend#420
- bpmn-io/bpmn-js#1802
- cpsoinos/nuxt-svgo#97
- skbkontur/db-viewer#80
- woowacourse/perf-basecamp#68
- mia-platform/design-system#477
- apache/superset#29787
- dialpad/dialtone#420
- user-interviews/ui-design-system#1289
- CorentinTh/it-tools#1369
- deankerr/corale#5
---
# Icon payload bloat

> **Risk tier:** medium · **Applies to:** EDS, CS, Headless · **CWV metric:** LCP, INP

## What this addresses

A JavaScript icon registry that imports every SVG definition can add unused icons to an application bundle. Replacing registry lookups with static, per-icon module imports can allow an ESM-aware build to remove unused SVG definitions when the package and production build support tree shaking.

## When to apply / when to skip
**Apply when:**
- Bundle analysis identifies an icon package, SVG registry, or icon-map module as meaningful JavaScript payload on the audited route.
- The rendered icons on the route can be inventoried and resolved to a finite set of statically known icon modules.
- The icon package publishes ESM modules and the production build output confirms unused icons are removed.
- Dynamic icon names are confined to a small known set that can be explicitly mapped without importing the full registry.

**Skip when:**
- Icons are delivered as a single external SVG sprite or server-rendered inline SVG with no JavaScript registry payload.
- The current clientlib or headless build output does not preserve ESM imports or cannot demonstrate tree shaking.
- Icon selection is genuinely open-ended at runtime, such as author-provided arbitrary icon identifiers with no bounded allowlist.
- The affected icon module is already a small, route-scoped chunk and bundle analysis shows no meaningful unused-icon payload.

## Recommended approaches

### Good: Import only the icons rendered by an EDS block

Keep each icon in a block-relative module and import only the definitions the block needs.

```javascript
// Good: blocks/search/search.js
import searchIcon from './icons/search.js';
import closeIcon from './icons/close.js';

function createDecorativeIcon(iconFactory) {
  const icon = iconFactory();
  icon.setAttribute('aria-hidden', 'true');
  icon.setAttribute('focusable', 'false');
  return icon;
}

export default function decorate(block) {
  const searchButton = block.querySelector('button[type="submit"]');
  const closeButton = block.querySelector('[data-search-close]');

  searchButton.prepend(createDecorativeIcon(searchIcon));
  closeButton.prepend(createDecorativeIcon(closeIcon));
}
```

```javascript
// blocks/search/icons/search.js
export default function searchIcon() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.innerHTML = '<path d="M10.5 3a7.5 7.5 0 1 0 4.7 13.3L21 22l1-1-5.7-5.7A7.5 7.5 0 0 0 10.5 3Z"/>';
  return svg;
}
```

Static module references allow compatible ESM builds to identify the icon modules used by the search block. Keep an accessible name on icon-only controls while changing the icon implementation.

### Load a non-critical EDS enhancement only when its block is needed

For a below-the-fold block whose icon-heavy interaction is not needed for initial rendering, load the block-relative feature module after it enters the viewport.

```javascript
// blocks/share/share.js
export default function decorate(block) {
  const observer = new IntersectionObserver(async (entries) => {
    if (!entries[0].isIntersecting) return;

    const { decorateShareActions } = await import('./share-actions.js');
    decorateShareActions(block);
    observer.disconnect();
  }, { rootMargin: '200px' });

  observer.observe(block);
}
```

```javascript
// blocks/share/share-actions.js
import copyIcon from './icons/copy.js';
import emailIcon from './icons/email.js';

export function decorateShareActions(block) {
  block.querySelector('[data-share="copy"]').prepend(copyIcon());
  block.querySelector('[data-share="email"]').prepend(emailIcon());
}
```

Keep the imported module free of wildcard icon imports. Do not use this approach for an above-the-fold control that must be interactive immediately.

### Keep CS clientlib categories component-scoped

Use the standard AEM clientlib structure to keep component-specific icon code out of global categories. Verify the publish asset after the frontend build has processed any ESM source.

```xml
<!-- Good: apps/site/clientlibs/components/search/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.components.search]"
          dependencies="[site.base]"
          allowProxy="{Boolean}true"/>
```

```text
# Good: apps/site/clientlibs/components/search/js.txt
#base=js
search.js
```

```javascript
// apps/site/clientlibs/components/search/js/search.js
(function () {
  function appendSearchIcon(button) {
    if (!button) return;
    button.insertAdjacentHTML(
      'afterbegin',
      '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M10.5 3a7.5 7.5 0 1 0 4.7 13.3L21 22l1-1-5.7-5.7A7.5 7.5 0 0 0 10.5 3Z"/></svg>',
    );
  }

  function appendCloseIcon(button) {
    if (!button) return;
    button.insertAdjacentHTML(
      'afterbegin',
      '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>',
    );
  }

  document.querySelectorAll('.cmp-search').forEach((component) => {
    appendSearchIcon(component.querySelector('.cmp-search__submit'));
    appendCloseIcon(component.querySelector('.cmp-search__clear'));
  });
}());
```

Verify the emitted publish bundle, not merely source imports, because the frontend build and clientlib aggregation determine whether unused icon modules are removed.

### Replace runtime icon names with a bounded explicit map

When an authored value selects among a small approved icon set, have a Sling Model normalize the value and emit an explicit identifier. The client code can then use a small explicit branch rather than dynamically indexing a package-wide icon object.

```java
// core/src/main/java/com/site/core/models/ActionIconModel.java
@Model(adaptables = SlingHttpServletRequest.class)
public class ActionIconModel {
  @ValueMapValue
  private String icon;

  public String getIcon() {
    if ("download".equals(icon) || "external".equals(icon)) {
      return icon;
    }
    return "external";
  }
}
```

```html
<!-- apps/site/components/action/action.html -->
<sly data-sly-use.model="com.site.core.models.ActionIconModel"></sly>
<a class="cmp-action" data-action-icon="${model.icon}" href="${properties.link}">
  <span class="cmp-action__label">${properties.label}</span>
</a>
```

```javascript
// Component-specific frontend source, compiled into its scoped clientlib
import { appendDownloadIcon } from './icons/download.js';
import { appendExternalIcon } from './icons/external.js';

document.querySelectorAll('.cmp-action').forEach((action) => {
  if (action.dataset.actionIcon === 'download') {
    appendDownloadIcon(action);
  } else {
    appendExternalIcon(action);
  }
});
```

The explicit branch keeps the component's icon options bounded rather than dynamically indexing an unrestricted icon catalog.

## Anti-patterns

### Namespace-importing an icon registry

```javascript
// Bad: the icon is selected at runtime
import * as icons from './icons/index.js';

export default function decorate(block) {
  const iconName = block.dataset.icon;
  block.querySelector('button').prepend(icons[iconName]());
}
```

**Why this is bad:** A runtime property lookup can prevent tree shaking because the build may need to retain every icon that could be selected from the registry.

### Caching every SVG export into a runtime map

```javascript
// Bad: blocks/icon-picker/icon-picker.js eagerly registers the complete SVG catalog
import * as InternalSvgIcons from './svg/index.js';

export default function decorate(block) {
  const iconMap = {};

  Object.keys(InternalSvgIcons).forEach((name) => {
    iconMap[name] = InternalSvgIcons[name];
  });

  const icon = iconMap[block.dataset.icon];
  if (icon) {
    block.querySelector('button').prepend(icon());
  }
}
```

**Why this is bad:** Enumerating all SVG exports can make every icon reachable, retaining the complete registry even when the page uses only one or two icons.

### Adding a broad icon clientlib to the page template

```html
<!-- Bad: every page receives the complete icon registry clientlib -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
<sly data-sly-call="${clientlib.all @ categories='site.base,site.icons.all'}"/>
```

```xml
<!-- Bad: a global category includes the registry on every template -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.icons.all]"
          dependencies="[site.base]"/>
```

**Why this is bad:** This configuration includes the icon registry clientlib on every template, including templates that may not render those icons.

## Flavor-specific notes

### EDS

Place icon modules beside the block that consumes them, such as `blocks/search/icons/search.js`, rather than in a site-wide `icons/index.js` registry. Use direct static imports for icons needed during block decoration. Use block-relative `import()` only for genuinely non-critical, viewport-triggered enhancements, and keep the imported module free of wildcard icon imports.

### CS

AEM clientlibs alone do not guarantee tree shaking. Confirm that the frontend pipeline produces tree-shakeable output before changing imports, then inspect the compiled publish asset for the target clientlib category. Do not move an icon registry into `site.base` merely to simplify component imports; retain category and template scoping.

### Headless

Apply the same static-import rule in the client-rendered frontend that consumes AEM Content Fragment or GraphQL data. Treat author-provided icon fields as bounded presentation values: normalize them to a known allowlist in the frontend or content contract, and map that allowlist to direct icon modules rather than dynamically indexing a package-wide icon object.