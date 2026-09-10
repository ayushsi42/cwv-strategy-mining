applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

## Load an optional graph library on user interaction

### Anti-pattern

```html
<!-- EDS document/template: loaded for every visitor, even when the graph tab is never opened -->
<script src="/scripts/vendors/mermaid.min.js"></script>
```

```xml
<!-- CS/AMS: /apps/my-site/clientlibs/graph/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.graph]"
    allowProxy="{Boolean}true"/>
```

```text
# CS/AMS: /apps/my-site/clientlibs/graph/js.txt
mermaid.min.js
graph.js
```

```html
<!-- CS/AMS page component: the clientlib, including Mermaid, is loaded for every visitor -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.all @ categories='site.graph'}"></sly>
```

**Why this is bad:** This places the Mermaid dependency on the critical path for every visitor. In the cited implementation, lazy-loading moved approximately 700 KB gzipped off the critical path for visitors who never open the Math tab.

### Approach

Load the dependency when the visitor requests the graph feature.

```js
// EDS: blocks/graph/graph.js
let mermaidPromise;

function loadMermaidLib() {
  mermaidPromise ||= import('./mermaid.js');
  return mermaidPromise;
}

export default function decorate(block) {
  const graphTab = block.querySelector('[data-graph-tab]');

  if (!graphTab) return;

  graphTab.addEventListener('click', async () => {
    try {
      await loadMermaidLib();
    } catch (error) {
      graphTab.setAttribute('role', 'alert');
      throw error;
    }
  }, { once: true });
}
```

```xml
<!-- CS/AMS: /apps/my-site/clientlibs/graph/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.graph]"
    allowProxy="{Boolean}true"/>
```

```text
# CS/AMS: /apps/my-site/clientlibs/graph/js.txt
graph.js
```

```js
// CS/AMS: /apps/my-site/clientlibs/graph/graph.js
(() => {
  let mermaidPromise;

  function loadMermaidLib() {
    if (mermaidPromise) return mermaidPromise;

    mermaidPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/etc.clientlibs/my-site/clientlibs/graph/resources/mermaid.min.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });

    return mermaidPromise;
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-graph-tab]').forEach((graphTab) => {
      graphTab.addEventListener('click', async () => {
        try {
          await loadMermaidLib();
        } catch (error) {
          graphTab.setAttribute('role', 'alert');
          throw error;
        }
      }, { once: true });
    });
  });
})();
```

```html
<!-- CS/AMS page component: load only the lightweight graph interaction clientlib -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.all @ categories='site.graph'}"></sly>
```

Apply this pattern to optional graph visualizations so visitors who do not open the graph tab do not load Mermaid during the initial page load.

> **Source PRs** — **approach:** ibenian/algebench#123, gatsbyjs/gatsby#35403, newrelic/newrelic-browser-agent#435, adobecom/express#930, cs-soc-tudublin/Plume#23 · **anti-pattern:** Fashion-App-NG/frontend#80, mozilla/addons-frontend#12001, hlxsites/blogs-keysight2#1, ant-design/ant-design#52300