applicable_flavors for the playbook this content is being added to: ['eds', 'cs']

### Use geometry-matched skeletons while async block data loads

When a block fetches data before rendering cards, rows, or controls, consider rendering a skeleton or
placeholder while data is unavailable. Reserve space that is appropriate for the eventual content,
especially when replacing a small loading indicator with a wider form, grid, or list.

Use the same layout classes for the loading and loaded states where practical.

```js
// EDS: blocks/models/models.js
import { createTag } from '../../scripts/aem.js';

function createSkeletonCard() {
  const card = createTag('li', {
    class: 'models-card models-card-skeleton',
    'aria-hidden': 'true',
  });

  card.append(
    createTag('div', { class: 'models-card-media' }),
    createTag('div', { class: 'models-card-line models-card-line-title' }),
    createTag('div', { class: 'models-card-line' }),
    createTag('div', { class: 'models-card-line models-card-line-short' }),
  );

  return card;
}

function createTextElement(tagName, className, text) {
  const element = createTag(tagName, { class: className });
  element.textContent = text || '';
  return element;
}

function renderModelCard(model) {
  const card = createTag('li', { class: 'models-card' });
  const media = createTag('div', { class: 'models-card-media' });

  if (model.image) {
    const image = createTag('img', {
      src: model.image,
      alt: model.imageAlt || '',
      loading: 'lazy',
    });
    media.append(image);
  }

  card.append(
    media,
    createTextElement('h3', 'models-card-title', model.name),
    createTextElement('p', 'models-card-description', model.description),
  );

  return card;
}

export default async function decorate(block) {
  const list = createTag('ul', {
    class: 'models-list models-list-skeleton',
    'aria-busy': 'true',
  });

  const skeletonCount = 6;
  Array.from({ length: skeletonCount }, createSkeletonCard).forEach((card) => list.append(card));
  block.replaceChildren(list);

  const response = await fetch('/models.json');
  if (!response.ok) throw new Error(`Unable to load models: ${response.status}`);

  const { data: models } = await response.json();

  list.classList.remove('models-list-skeleton');
  list.removeAttribute('aria-busy');
  list.replaceChildren(...models.map(renderModelCard));
}
```

```html
<!-- CS: ui.apps/src/main/content/jcr_root/apps/example/components/models/models.html -->
<sly
  data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
  data-sly-call="${clientlib.css @ categories='example.models'}"></sly>

<div
  class="models"
  data-models-endpoint="${properties.modelsEndpoint @ context='uri'}">
</div>

<sly data-sly-call="${clientlib.js @ categories='example.models'}"></sly>
```

```xml
<!-- CS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/models/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.models]"
    allowProxy="{Boolean}true"/>
```

```js
// CS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/models/models.js
(() => {
  function createElement(tagName, className, text) {
    const element = document.createElement(tagName);
    element.className = className;
    if (text) element.textContent = text;
    return element;
  }

  function createSkeletonCard() {
    const card = createElement('li', 'models-card models-card-skeleton');
    card.setAttribute('aria-hidden', 'true');

    card.append(
      createElement('div', 'models-card-media'),
      createElement('div', 'models-card-line models-card-line-title'),
      createElement('div', 'models-card-line'),
      createElement('div', 'models-card-line models-card-line-short'),
    );

    return card;
  }

  function renderModelCard(model) {
    const card = createElement('li', 'models-card');
    const media = createElement('div', 'models-card-media');

    if (model.image) {
      const image = document.createElement('img');
      image.src = model.image;
      image.alt = model.imageAlt || '';
      image.loading = 'lazy';
      media.append(image);
    }

    card.append(
      media,
      createElement('h3', 'models-card-title', model.name),
      createElement('p', 'models-card-description', model.description),
    );

    return card;
  }

  async function decorateModels(root) {
    const endpoint = root.dataset.modelsEndpoint;
    const list = createElement('ul', 'models-list models-list-skeleton');
    list.setAttribute('aria-busy', 'true');

    Array.from({ length: 6 }, createSkeletonCard).forEach((card) => list.append(card));
    root.replaceChildren(list);

    const response = await fetch(endpoint);
    if (!response.ok) throw new Error(`Unable to load models: ${response.status}`);

    const { data: models } = await response.json();

    list.classList.remove('models-list-skeleton');
    list.removeAttribute('aria-busy');
    list.replaceChildren(...models.map(renderModelCard));
  }

  document.querySelectorAll('.models[data-models-endpoint]').forEach((root) => {
    decorateModels(root);
  });
})();
```

```css
/* EDS: blocks/models/models.css
   CS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/models/models.css */
.models-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(var(--models-card-min-inline-size), 1fr));
  gap: var(--models-grid-gap);
}

.models-card {
  display: grid;
  align-content: start;
  min-block-size: var(--models-card-min-block-size);
  padding: var(--models-card-padding);
}

.models-card-media {
  aspect-ratio: var(--models-card-media-aspect-ratio);
  overflow: hidden;
  background: #e7e7e7;
}

.models-card-media img {
  inline-size: 100%;
  block-size: 100%;
  object-fit: cover;
}

.models-card-title,
.models-card-description,
.models-card-line {
  margin-block: var(--models-card-spacing) 0;
}

.models-card-title {
  min-block-size: var(--models-title-min-block-size);
}

.models-card-description {
  min-block-size: var(--models-description-min-block-size);
}

.models-card-line {
  block-size: var(--models-line-block-size);
  border-radius: var(--models-line-radius);
  background: #e7e7e7;
}

.models-card-line-title {
  inline-size: 70%;
  block-size: var(--models-title-min-block-size);
}

.models-card-line-short {
  inline-size: 45%;
}

.models-list-skeleton .models-card-media,
.models-list-skeleton .models-card-line {
  background-image: linear-gradient(90deg, #e7e7e7 25%, #f3f3f3 50%, #e7e7e7 75%);
  background-size: 200% 100%;
  animation: models-skeleton-shimmer 1.2s linear infinite;
}

@keyframes models-skeleton-shimmer {
  to { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .models-list-skeleton .models-card-media,
  .models-list-skeleton .models-card-line {
    animation: none;
  }
}
```

Choose placeholder dimensions and column behavior based on the loaded component at each breakpoint.
If the loaded state adds substantially more height, different columns, or controls that are not
represented while loading, layout shifts can still occur.

### Spinner-only fallbacks for variable-size async regions

```js
// EDS: blocks/models/models.js
// The initial block has only spinner dimensions; loaded content may have different dimensions.
export default async function decorate(block) {
  block.innerHTML = '<div class="loading-spinner">Loading models…</div>';

  const response = await fetch('/models.json');
  const { data: models } = await response.json();

  block.innerHTML = `
    <ul class="models-list">
      ${models.map((model) => `<li class="models-card">${model.name}</li>`).join('')}
    </ul>
  `;
}
```

```html
<!-- CS: ui.apps/src/main/content/jcr_root/apps/example/components/models/models.html -->
<sly
  data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
  data-sly-call="${clientlib.css @ categories='example.models'}"></sly>

<div
  class="models"
  data-models-endpoint="${properties.modelsEndpoint @ context='uri'}">
</div>

<sly data-sly-call="${clientlib.js @ categories='example.models'}"></sly>
```

```xml
<!-- CS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/models/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.models]"
    allowProxy="{Boolean}true"/>
```

```js
// CS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/models/models.js
// The initial component has only spinner dimensions; loaded content may have different dimensions.
(() => {
  async function decorateModels(root) {
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    spinner.textContent = 'Loading models…';
    root.replaceChildren(spinner);

    const response = await fetch(root.dataset.modelsEndpoint);
    const { data: models } = await response.json();

    const list = document.createElement('ul');
    list.className = 'models-list';

    models.forEach((model) => {
      const card = document.createElement('li');
      card.className = 'models-card';
      card.textContent = model.name;
      list.append(card);
    });

    root.replaceChildren(list);
  }

  document.querySelectorAll('.models[data-models-endpoint]').forEach((root) => {
    decorateModels(root);
  });
})();
```

**Why this is bad:** A spinner or small loading message may not reserve enough space for a loaded
form, product grid, or card list. Replacing it can shift surrounding content vertically. If the
loading state is centered but the loaded interface is wider, the block can also appear to move
horizontally. Use a placeholder that reserves suitable space, such as a skeleton, reserved height,
or loading message sized for the eventual region.

> **Source PRs** — **approach:** redpanda-data/console#2043, vtex-sites/base.store#317, kwonhygge/react-todo-app#2, RedHat-UX/red-hat-design-system#2043, guardian/dotcom-rendering#8570 · **anti-pattern:** loculus-project/loculus#3710, aemsites/hubblehomes-com#36, aemsites/stericycle-shared#445, atlassian/landkid#169