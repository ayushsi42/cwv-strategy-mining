### Isolate feature-only dependencies from page-load bundles

Keep feature-specific libraries and styles out of global page-load assets where possible. In EDS, load feature code when the corresponding block is decorated.

```js
// blocks/timetree/timetree.js (EDS)
// Good — the graph module is loaded only when this block is decorated
export default async function decorate(block) {
  const {
    select,
    forceSimulation,
    forceManyBody,
    forceCenter,
  } = await import('./timetree-graph.js');

  const response = await fetch('/data/timetree.json');
  const data = await response.json();

  renderTree(block, {
    select,
    forceSimulation,
    forceManyBody,
    forceCenter,
    data,
  });
}
```

```xml
<!-- ui.apps/src/main/content/jcr_root/apps/site/clientlibs/timetree/.content.xml
     (AEM as a Cloud Service / AEM 6.5 AMS) -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.timetree]"
    allowProxy="{Boolean}true"/>
```

```text
# ui.apps/src/main/content/jcr_root/apps/site/clientlibs/timetree/js.txt
timetree-graph.js
timetree.js
```

```html
<!-- apps/site/components/timetree/timetree.html
     Load this category only when the Timetree component is rendered. -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html" />
<div class="timetree" data-timetree-data="/content/dam/site/data/timetree.json"></div>
<sly data-sly-call="${clientlib.js @ categories='site.timetree'}" />
```

```js
// ui.apps/src/main/content/jcr_root/apps/site/clientlibs/timetree/timetree.js
// The graph dependency is bundled only in the feature-specific client library.
(() => {
  async function renderTimetree(block) {
    const response = await fetch(block.dataset.timetreeData);
    const data = await response.json();

    window.TimeTreeGraph.render(block, data);
  }

  document.querySelectorAll('.timetree').forEach((block) => {
    renderTimetree(block);
  });
})();
```

### Loading feature CSS after initializing a block

```js
// blocks/interactive-elements/interactive-elements.js (EDS)
// CSS is requested after interactive initialization
import { loadCSS } from '../../scripts/aem.js';

export default async function decorate(block) {
  interactiveInit(block);

  loadCSS('/features/interactive-elements/interactive-elements.css');

  const { default: setInteractiveFirefly } = await import(
    '../../features/firefly/firefly-interactive.js'
  );
  setInteractiveFirefly(block);
}
```

```xml
<!-- ui.apps/src/main/content/jcr_root/apps/site/clientlibs/interactive-init/.content.xml
     (AEM as a Cloud Service / AEM 6.5 AMS) -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.interactive-init]"
    allowProxy="{Boolean}true"/>
```

```text
# ui.apps/src/main/content/jcr_root/apps/site/clientlibs/interactive-init/js.txt
interactive-init.js
```

```xml
<!-- ui.apps/src/main/content/jcr_root/apps/site/clientlibs/interactive-feature/.content.xml -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.interactive-feature]"
    allowProxy="{Boolean}true"/>
```

```text
# ui.apps/src/main/content/jcr_root/apps/site/clientlibs/interactive-feature/css.txt
interactive-elements.css

# ui.apps/src/main/content/jcr_root/apps/site/clientlibs/interactive-feature/js.txt
firefly-interactive.js
```

```html
<!-- apps/site/components/interactive-elements/interactive-elements.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html" />
<div class="interactive-elements"></div>
<sly data-sly-call="${clientlib.js @ categories='site.interactive-init'}" />
```

```js
// ui.apps/src/main/content/jcr_root/apps/site/clientlibs/interactive-init/interactive-init.js
(() => {
  function loadFeatureStylesheet() {
    const stylesheet = document.createElement('link');
    stylesheet.rel = 'stylesheet';
    stylesheet.href = '/etc.clientlibs/site/clientlibs/interactive-feature.css';
    document.head.append(stylesheet);
  }

  function loadFeatureScript() {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/etc.clientlibs/site/clientlibs/interactive-feature.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.append(script);
    });
  }

  document.querySelectorAll('.interactive-elements').forEach(async (element) => {
    interactiveInit(element);

    loadFeatureStylesheet();
    await loadFeatureScript();

    window.setInteractiveFirefly(element);
  });
})();
```

**Evidence note:** In the Firefly PR, reviewer feedback says that importing the CSS this way adds CLS. The code calls `interactiveInit(el)` before `loadStyle(...)`, and the added stylesheet includes layout rules such as dimensions and positioning. The evidence does not quantify the shift or establish that every late-loaded stylesheet will cause it.

> **Source PRs** — **approach:** Automattic/jetpack#26666, blockonomics/woocommerce-plugin#276, digi-serve/ab_platform_web#443, Princeton-CDH/lenape-timetree#23, elastic/kibana#206533 · **anti-pattern:** adobecom/cc#110, hlxsites/blogs-keysight2#1, adobe/express-website#788