### Use shape-matched skeletons for async EDS blocks

A spinner or centered “Loading…” message may not reserve the footprint of the final card grid, form, or widget. When fetched content replaces it, the container can grow and shift content below it.

```js
// EDS: blocks/models/models.js
// Bad — the spinner may not reserve the final grid's space
function renderModelsGrid(models) {
  const grid = document.createElement('ul');
  grid.className = 'models-grid';

  models.forEach((model) => {
    const item = document.createElement('li');
    item.className = 'model-card';
    item.textContent = model.title;
    grid.append(item);
  });

  return grid;
}

export default async function decorate(block) {
  block.innerHTML = '<p class="loading">Loading models…</p>';

  const response = await fetch('/models.json');
  const models = await response.json();

  block.replaceChildren(renderModelsGrid(models));
}

// CS: clientlibs/site/models/models.js
// Bad — this clientlib is loaded through the site.models category
(() => {
  function renderModelsGrid(models) {
    const grid = document.createElement('ul');
    grid.className = 'models-grid';

    models.forEach((model) => {
      const item = document.createElement('li');
      item.className = 'model-card';
      item.textContent = model.title;
      grid.append(item);
    });

    return grid;
  }

  async function loadModels(block) {
    block.innerHTML = '<p class="loading">Loading models…</p>';

    const endpoint = block.dataset.modelsEndpoint || '/models.json';
    const response = await fetch(endpoint);
    const models = await response.json();

    block.replaceChildren(renderModelsGrid(models));
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.models').forEach(loadModels);
  });
})();
```

**Why this is bad:** If the loading message is much smaller than the loaded card grid, replacing it can expand the block after first render and shift content below it.

Render a skeleton with the same grid columns, image ratio, padding, and bounded text rows as the loaded component. Build it before awaiting the data request.

```js
// EDS: blocks/models/models.js
// Good — skeleton cards reserve approximately the same geometry as loaded cards
function createElement(tag, className) {
  const element = document.createElement(tag);
  element.className = className;
  return element;
}

function createCardSkeleton() {
  const card = createElement('li', 'model-card model-card-skeleton');
  card.setAttribute('aria-hidden', 'true');

  const image = createElement('div', 'model-card-image skeleton-shimmer');
  const content = createElement('div', 'model-card-content');

  const title = createElement('div', 'skeleton-line skeleton-line-title skeleton-shimmer');
  const meta = createElement('div', 'skeleton-line skeleton-line-meta skeleton-shimmer');
  const action = createElement('div', 'skeleton-line skeleton-line-action skeleton-shimmer');

  content.append(title, meta, action);
  card.append(image, content);

  return card;
}

function renderModelCard(model) {
  const card = createElement('li', 'model-card');

  const image = document.createElement('img');
  image.className = 'model-card-image';
  image.src = model.image;
  image.alt = model.title;
  image.width = 640;
  image.height = 360;

  const content = createElement('div', 'model-card-content');
  const title = document.createElement('h3');
  title.className = 'model-card-title';
  title.textContent = model.title;

  const meta = document.createElement('p');
  meta.className = 'model-card-meta';
  meta.textContent = model.category;

  content.append(title, meta);
  card.append(image, content);

  return card;
}

export default async function decorate(block) {
  const placeholderCount = Math.max(block.querySelectorAll(':scope > div').length, 1);
  const grid = document.createElement('ul');

  grid.className = 'models-grid';
  grid.setAttribute('aria-busy', 'true');

  for (let index = 0; index < placeholderCount; index += 1) {
    grid.append(createCardSkeleton());
  }

  block.replaceChildren(grid);

  const response = await fetch('/models.json');
  if (!response.ok) throw new Error(`Unable to load models: ${response.status}`);

  const models = await response.json();
  grid.replaceChildren(...models.map(renderModelCard));
  grid.removeAttribute('aria-busy');
}

// CS: clientlibs/site/models/models.js
// Good — this clientlib is loaded through the site.models category
(() => {
  function createElement(tag, className) {
    const element = document.createElement(tag);
    element.className = className;
    return element;
  }

  function createCardSkeleton() {
    const card = createElement('li', 'model-card model-card-skeleton');
    card.setAttribute('aria-hidden', 'true');

    const image = createElement('div', 'model-card-image skeleton-shimmer');
    const content = createElement('div', 'model-card-content');

    const title = createElement('div', 'skeleton-line skeleton-line-title skeleton-shimmer');
    const meta = createElement('div', 'skeleton-line skeleton-line-meta skeleton-shimmer');
    const action = createElement('div', 'skeleton-line skeleton-line-action skeleton-shimmer');

    content.append(title, meta, action);
    card.append(image, content);

    return card;
  }

  function renderModelCard(model) {
    const card = createElement('li', 'model-card');

    const image = document.createElement('img');
    image.className = 'model-card-image';
    image.src = model.image;
    image.alt = model.title;
    image.width = 640;
    image.height = 360;

    const content = createElement('div', 'model-card-content');
    const title = document.createElement('h3');
    title.className = 'model-card-title';
    title.textContent = model.title;

    const meta = document.createElement('p');
    meta.className = 'model-card-meta';
    meta.textContent = model.category;

    content.append(title, meta);
    card.append(image, content);

    return card;
  }

  async function loadModels(block) {
    const placeholderCount = Math.max(block.children.length, 1);
    const grid = document.createElement('ul');

    grid.className = 'models-grid';
    grid.setAttribute('aria-busy', 'true');

    for (let index = 0; index < placeholderCount; index += 1) {
      grid.append(createCardSkeleton());
    }

    block.replaceChildren(grid);

    const endpoint = block.dataset.modelsEndpoint || '/models.json';
    const response = await fetch(endpoint);
    if (!response.ok) throw new Error(`Unable to load models: ${response.status}`);

    const models = await response.json();
    grid.replaceChildren(...models.map(renderModelCard));
    grid.removeAttribute('aria-busy');
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.models').forEach((block) => {
      loadModels(block).catch((error) => {
        block.textContent = error.message;
      });
    });
  });
})();
```

```html
<!-- CS: apps/example/components/models/models.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html" />
<sly data-sly-call="${clientlib.css @ categories='site.models'}" />

<div class="models" data-models-endpoint="${properties.modelsEndpoint @ context='uri'}">
  <div></div>
  <div></div>
  <div></div>
</div>

<sly data-sly-call="${clientlib.js @ categories='site.models'}" />
```

```xml
<!-- CS: apps/example/clientlibs/models/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.models]"
    allowProxy="{Boolean}true"/>
```

```text
# CS: apps/example/clientlibs/models/js.txt
models.js

# CS: apps/example/clientlibs/models/css.txt
models.css
```

```css
/* EDS: blocks/models/models.css */
/* CS: clientlibs/site/models/models.css */
/* Loaded cards and skeletons share the same geometry. */
.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
  gap: 1.5rem;
}

.model-card {
  display: grid;
  grid-template-rows: auto 1fr;
  overflow: hidden;
}

.model-card-image {
  aspect-ratio: 16 / 9;
  inline-size: 100%;
  object-fit: cover;
}

.model-card-content {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
}

.model-card-title {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.skeleton-line {
  block-size: 1rem;
  border-radius: 0.25rem;
}

.skeleton-line-title {
  inline-size: 80%;
  block-size: 2.5rem;
}

.skeleton-line-meta {
  inline-size: 55%;
}

.skeleton-line-action {
  inline-size: 40%;
}

.skeleton-shimmer {
  background: linear-gradient(90deg, #e8e8e8 25%, #f3f3f3 37%, #e8e8e8 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.2s linear infinite;
}

@keyframes skeleton-shimmer {
  to {
    background-position: -100% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-shimmer {
    animation: none;
  }
}
```

The shimmer is optional visual feedback. Reserving space with dimensions that closely match the loaded component can reduce layout shifts; match the loaded component’s image ratio, text-row limit, padding, and breakpoint-specific grid rules.

> **Source PRs** — **approach:** redpanda-data/console#2043, vtex-sites/base.store#317, kwonhygge/react-todo-app#2, RedHat-UX/red-hat-design-system#2043, guardian/dotcom-rendering#8570 · **anti-pattern:** loculus-project/loculus#3710, aemsites/hubblehomes-com#36, aemsites/stericycle-shared#445, atlassian/landkid#169