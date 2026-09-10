applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### Do not eagerly load optional Worker or WASM features

**Bad — CS/AMS: loading optional feature bootstrap from a site-wide clientlib**

```xml
<!-- /apps/site/clientlibs/clientlib-site/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.base]"
          allowProxy="{Boolean}true"/>
```

```text
# /apps/site/clientlibs/clientlib-site/js.txt

agent/ai-engine.js
```

```javascript
// agent/ai-engine.js — runs on every page that loads site.base
const worker = new Worker(
  '/etc.clientlibs/site/clientlibs/clientlib-site/resources/route-worker.js',
);

worker.postMessage({ type: 'load-model' });
```

**Why this is bad:** Workers can offload work from the main thread, which can help keep the UI responsive. However, this code creates the Worker and initializes the feature whenever the global clientlib loads, including on pages where the feature is not used.

**Good — load the feature from the component interaction that needs it**

```html
<!-- CS/AMS component HTL -->
<sly
  data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
  data-sly-call="${clientlib.js @ categories='site.route-assistant'}" />
```

```xml
<!-- /apps/site/clientlibs/clientlib-route-assistant/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[site.route-assistant]"
          allowProxy="{Boolean}true"/>
```

```text
# /apps/site/clientlibs/clientlib-route-assistant/js.txt

agent/ai-engine.js
```

```javascript
// agent/ai-engine.js — runs only when the component is present
document.querySelectorAll('[data-route-assistant]').forEach((component) => {
  component.querySelector('button').addEventListener('click', () => {
    const worker = new Worker(
      '/etc.clientlibs/site/clientlibs/clientlib-route-assistant/resources/route-worker.js',
    );

    worker.postMessage({ type: 'load-model' });
  }, { once: true });
});
```

```javascript
// EDS block decoration — load optional code only after interaction
export default function decorate(block) {
  const button = block.querySelector('button');

  button.addEventListener('click', async () => {
    const { startRouteAssistant } = await import('./route-assistant.js');
    startRouteAssistant(block);
  }, { once: true });
}
```

```javascript
// route-assistant.js
export function startRouteAssistant(block) {
  const worker = new Worker(
    new URL('./route-worker.js', import.meta.url),
    { type: 'module' },
  );

  worker.postMessage({ type: 'load-model' });
}
```

> **Source PRs** — **approach:** JULIANJUAREZMX01/MueveCancun#492, IDEMSInternational/parenting-app-ui#1926, osmosis-labs/osmosis-frontend#1936, rhysmorgan134/node-CarPlay#17, code-dot-org/code-dot-org#60463 · **anti-pattern:** kamiazya/web-csv-toolbox#551