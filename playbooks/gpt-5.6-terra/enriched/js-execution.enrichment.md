### Use transferable streams for large browser inputs

For worker-backed parsing in browsers, use transferable streams when available so parsing can be offloaded from the main thread with zero-copy data transfer.

```javascript
// blocks/data-import/data-import.js
export default function decorate(block) {
  const input = block.querySelector('input[type="file"]');
  const status = block.querySelector('[data-status]');

  input.addEventListener('change', async () => {
    const [file] = input.files;
    if (!file) return;

    status.textContent = 'Processing…';

    const worker = new Worker(
      new URL('./data-import-worker.js', import.meta.url),
      { type: 'module' },
    );

    const stream = file.stream();

    worker.onmessage = ({ data }) => {
      status.textContent = `Imported ${data.rowCount} rows`;
      worker.terminate();
    };

    worker.onerror = () => {
      status.textContent = 'Import failed';
      worker.terminate();
    };

    // Transfer the stream to the worker for zero-copy browser data transfer.
    worker.postMessage({ stream }, [stream]);
  });
}
```

> **Source PRs** — **approach:** osmosis-labs/osmosis-frontend#1936, rhysmorgan134/node-CarPlay#17, code-dot-org/code-dot-org#60463, maxdeliso/typed-ski#37, woowacourse/perf-basecamp#147 · **anti-pattern:** kamiazya/web-csv-toolbox#551