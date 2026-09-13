### Offloading every operation to a Web Worker

```javascript
// EDS: blocks/csv-viewer/csv-viewer.js
// Bad — every block instance starts its own worker.
export default async function decorate(block) {
  const { renderTable } = await import('./render.js');
  const worker = new Worker(
    new URL('./parser.worker.js', import.meta.url),
    { type: 'module' },
  );

  const source = block.querySelector('textarea');
  source.addEventListener('input', () => {
    worker.postMessage({ csv: source.value });
  });

  worker.onmessage = ({ data }) => renderTable(block, data.rows);
}

// CS/AMS: ui.apps/.../clientlibs/csv-viewer/.content.xml
// <jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
//   xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
//   jcr:primaryType="cq:ClientLibraryFolder"
//   categories="[site.csv-viewer]"/>

// CS/AMS: ui.apps/.../components/csv-viewer/csv-viewer.html
// <sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"/>
// <sly data-sly-call="${clientlib.js @ categories='site.csv-viewer'}"/>
// <div class="csv-viewer"
//      data-worker-url="/etc.clientlibs/site/clientlibs/csv-viewer/resources/parser.worker.js">
//   <textarea class="csv-viewer__source"></textarea>
//   <div class="csv-viewer__output"></div>
// </div>

// CS/AMS: ui.apps/.../clientlibs/csv-viewer/js/csv-viewer.js
// Bad — each rendered component creates its own worker.
document.querySelectorAll('.csv-viewer').forEach((viewer) => {
  const worker = new Worker(viewer.dataset.workerUrl, { type: 'module' });
  const source = viewer.querySelector('.csv-viewer__source');

  source.addEventListener('input', () => {
    worker.postMessage({ csv: source.value });
  });

  worker.onmessage = ({ data }) => renderTable(viewer, data.rows);
});
```

**Why this is bad:** Worker execution is intended to offload parsing from the main thread, particularly for large CSV files where keeping the UI responsive is beneficial. Using a separate worker for every block instance is not necessary when a single worker can handle multiple concurrent parsing requests.

### Use a worker for substantial CSV parsing

Create a worker when parsing work should be moved off the main thread. Reuse the worker for requests from the block.

```javascript
// EDS: blocks/csv-viewer/parser-client.js
let worker;
let nextRequestId = 0;
const pendingRequests = new Map();

function getWorker() {
  if (!worker) {
    worker = new Worker(
      new URL('./parser.worker.js', import.meta.url),
      { type: 'module' },
    );

    worker.onmessage = ({ data }) => {
      const resolve = pendingRequests.get(data.requestId);

      if (resolve) {
        pendingRequests.delete(data.requestId);
        resolve(data.rows);
      }
    };
  }

  return worker;
}

export function parseCsv(csv) {
  const requestId = nextRequestId;
  nextRequestId += 1;

  return new Promise((resolve) => {
    pendingRequests.set(requestId, resolve);
    getWorker().postMessage({ csv, requestId });
  });
}

// EDS: blocks/csv-viewer/csv-viewer.js
export default async function decorate(block) {
  const [{ parseCsv }, { renderTable }] = await Promise.all([
    import('./parser-client.js'),
    import('./render.js'),
  ]);

  const source = block.querySelector('textarea');
  let latestRequestId = 0;

  source.addEventListener('input', async () => {
    const requestId = latestRequestId + 1;
    latestRequestId = requestId;

    const rows = await parseCsv(source.value);

    if (requestId === latestRequestId) {
      renderTable(block, rows);
    }
  });
}

// CS/AMS: ui.apps/.../clientlibs/csv-viewer/js/csv-viewer.js
(() => {
  let worker;
  let nextRequestId = 0;
  const pendingRequests = new Map();

  function getWorker(workerUrl) {
    if (!worker) {
      worker = new Worker(workerUrl, { type: 'module' });

      worker.onmessage = ({ data }) => {
        const resolve = pendingRequests.get(data.requestId);

        if (resolve) {
          pendingRequests.delete(data.requestId);
          resolve(data.rows);
        }
      };
    }

    return worker;
  }

  function parseCsv(csv, workerUrl) {
    const requestId = nextRequestId;
    nextRequestId += 1;

    return new Promise((resolve) => {
      pendingRequests.set(requestId, resolve);
      getWorker(workerUrl).postMessage({ csv, requestId });
    });
  }

  document.querySelectorAll('.csv-viewer').forEach((viewer) => {
    const source = viewer.querySelector('.csv-viewer__source');
    let latestRequestId = 0;

    source.addEventListener('input', async () => {
      const requestId = latestRequestId + 1;
      latestRequestId = requestId;

      const rows = await parseCsv(source.value, viewer.dataset.workerUrl);

      if (requestId === latestRequestId) {
        renderTable(viewer, rows);
      }
    });
  });
})();
```

> **Source PRs** — **approach:** JULIANJUAREZMX01/MueveCancun#492, IDEMSInternational/parenting-app-ui#1926, osmosis-labs/osmosis-frontend#1936, rhysmorgan134/node-CarPlay#17, code-dot-org/code-dot-org#60463 · **anti-pattern:** kamiazya/web-csv-toolbox#551