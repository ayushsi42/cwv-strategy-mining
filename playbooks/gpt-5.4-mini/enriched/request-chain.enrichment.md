### Lazy-load non-critical chunk details

When the page has a large, document-scoped list of chunks but only one chunk’s analysis is needed at a time, fetch the detailed payload on demand instead of loading every chunk up front.

```js
export default function decorate(block) {
  const workflowRunId = block.dataset.workflowRunId;
  const chunkIndex = block.dataset.chunkIndex;
  const container = document.createElement('div');
  const button = document.createElement('button');
  const status = document.createElement('span');
  let open = false;
  let data = null;
  let isLoading = false;

  button.textContent = 'Load chunk details';

  async function loadChunkDetails() {
    open = true;
    isLoading = true;
    button.disabled = true;
    status.textContent = 'Loading…';

    try {
      const response = await fetch(
        `/api/workflow-run/${workflowRunId}/chunk/${chunkIndex}`,
      );
      data = await response.json();
      render();
    } finally {
      isLoading = false;
      button.disabled = false;
      status.textContent = '';
    }
  }

  function render() {
    container.innerHTML = '';
    container.append(button, status);

    if (open && data) {
      const card = document.createElement('div');
      card.className = 'chunk-analysis-card';
      card.textContent = JSON.stringify(data);
      container.append(card);
    }
  }

  button.addEventListener('click', loadChunkDetails);
  render();
  block.replaceChildren(container);
}
```

This keeps the initial render focused on the summary view and defers the heavier per-chunk analysis until the user expands or selects a chunk.

**Bad example:**

```js
export default function decorate(block) {
  const workflowRunId = block.dataset.workflowRunId;
  const chunkIndex = block.dataset.chunkIndex;
  const container = document.createElement('div');
  const card = document.createElement('div');

  fetch(`/api/workflow-run/${workflowRunId}/chunk/${chunkIndex}`)
    .then((response) => response.json())
    .then((json) => {
      card.className = 'chunk-analysis-card';
      card.textContent = JSON.stringify(json);
      container.append(card);
    });

  block.replaceChildren(container);
}
```

**Why this is bad:** This fetches chunk details immediately on page load, even when the user may never open the chunk. That adds unnecessary work to the initial load and can delay the summary content.

**Good example:**

```js
export default function decorate(block) {
  const workflowRunId = block.dataset.workflowRunId;
  const chunkIndex = block.dataset.chunkIndex;
  const container = document.createElement('div');
  const button = document.createElement('button');
  const card = document.createElement('div');
  let open = false;

  button.textContent = 'Load chunk details';

  async function loadChunkDetails() {
    open = true;
    const response = await fetch(
      `/api/workflow-run/${workflowRunId}/chunk/${chunkIndex}`,
    );
    const json = await response.json();
    card.className = 'chunk-analysis-card';
    card.textContent = JSON.stringify(json);
    render();
  }

  function render() {
    container.innerHTML = '';
    container.append(button);
    if (open && card.textContent) {
      container.append(card);
    }
  }

  button.addEventListener('click', loadChunkDetails);
  render();
  block.replaceChildren(container);
}
```

> **Source PRs** — **approach:** agencyenterprise/ai-reviewer#149, vtex-sites/base.store#329, l2beat/tools#43, GoogleChrome/lighthouse#14804, adobecom/milo#78