## Load feature-specific libraries on interaction

For a large library used only by an optional UI feature, such as a graph visualization, load the library when the visitor opens that feature rather than on every page view. Cache the load promise so repeated interactions do not request the script again.

```js
// EDS: blocks/semantic-graph/semantic-graph.js
let mermaidPromise;

function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('./mermaid/mermaid.esm.min.mjs')
      .then(({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false });
        return mermaid;
      })
      .catch((error) => {
        mermaidPromise = null; // Allow a later interaction to retry.
        throw error;
      });
  }

  return mermaidPromise;
}

export default function decorate(block) {
  const openButton = block.querySelector('button');
  const diagram = block.querySelector('.graph-diagram');

  openButton.addEventListener('click', async () => {
    openButton.disabled = true;
    block.setAttribute('aria-busy', 'true');

    try {
      const mermaid = await loadMermaid();
      await mermaid.run({ nodes: [diagram] });
      block.classList.add('is-rendered');
    } catch (error) {
      block.classList.add('load-failed');
      console.error(error);
    } finally {
      openButton.disabled = false;
      block.removeAttribute('aria-busy');
    }
  });
}

// CS/AMS: ui.apps/src/main/content/jcr_root/apps/my-site/clientlibs/semantic-graph/semantic-graph.js
let mermaidPromise;

function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');

      script.src = '/etc.clientlibs/my-site/clientlibs/mermaid.js';
      script.async = true;
      script.onload = () => {
        window.mermaid.initialize({ startOnLoad: false });
        resolve(window.mermaid);
      };
      script.onerror = () => {
        mermaidPromise = null; // Allow a later interaction to retry.
        reject(new Error('Could not load graph renderer'));
      };

      document.head.append(script);
    });
  }

  return mermaidPromise;
}

document.querySelectorAll('.semantic-graph').forEach((block) => {
  const openButton = block.querySelector('button');
  const diagram = block.querySelector('.graph-diagram');

  openButton.addEventListener('click', async () => {
    openButton.disabled = true;
    block.setAttribute('aria-busy', 'true');

    try {
      const mermaid = await loadMermaid();
      await mermaid.run({ nodes: [diagram] });
      block.classList.add('is-rendered');
    } catch (error) {
      block.classList.add('load-failed');
      console.error(error);
    } finally {
      openButton.disabled = false;
      block.removeAttribute('aria-busy');
    }
  });
});

/*
CS/AMS clientlib structure:

apps/my-site/clientlibs/semantic-graph/.content.xml
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[my-site.semantic-graph]"
  allowProxy="{Boolean}true"/>

apps/my-site/clientlibs/semantic-graph/js.txt
semantic-graph.js

apps/my-site/clientlibs/mermaid/.content.xml
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[my-site.mermaid]"
  allowProxy="{Boolean}true"/>

apps/my-site/clientlibs/mermaid/js.txt
mermaid.min.js
*/
```

This preserves the feature for visitors who request it while keeping the library off the critical path for visitors who never use it.

## Eagerly loading a library for an optional feature

```js
// EDS: Bad — importing the graph library with the block makes it part of
// the block's initial JavaScript download.
import mermaid from './mermaid/mermaid.esm.min.mjs';

export default function decorate(block) {
  const openButton = block.querySelector('button');

  openButton.addEventListener('click', async () => {
    await mermaid.run({ nodes: [block.querySelector('.graph-diagram')] });
  });
}

/*
CS/AMS: Bad — when this clientlib category is included on every page, both
the feature code and the graph library are delivered before the visitor opens
the Graph feature.

apps/my-site/clientlibs/semantic-graph/js.txt
mermaid.min.js
semantic-graph.js

The semantic-graph clientlib is then included through its category in the page
clientlib configuration, causing Mermaid to load for every page view.
*/
```

**Why this is bad:** The library is loaded on every page even when the Graph tab is never used. Load it after the visitor opens the optional feature.

> **Source PRs** — **approach:** ibenian/algebench#123, gatsbyjs/gatsby#35403, newrelic/newrelic-browser-agent#435, adobecom/express#930, cs-soc-tudublin/Plume#23 · **anti-pattern:** Fashion-App-NG/frontend#80, mozilla/addons-frontend#12001, hlxsites/blogs-keysight2#1, ant-design/ant-design#52300