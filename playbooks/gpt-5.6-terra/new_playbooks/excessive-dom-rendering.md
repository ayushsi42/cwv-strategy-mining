---
issue_type: excessive-dom-rendering
applicable_flavors:
- eds
- cs
- ams
- headless
required_validation: []
forbidden_techniques: []
risk_tier: medium
source_prs:
- greedy-team/react-todo-list#24
- mui/mui-x#22123
- NextCenturyCorporation/itm-evaluation-dashboard#513
- hirosystems/stacks-wallet-web#2078
- input-output-hk/daedalus#2924
- openline-ai/openline-customer-os#2427
- ant-design/ant-design#44349
- rango-exchange/rango-client#474
- metrom-xyz/monorepo#116
- bitwarden/clients#10113
---
# Excessive DOM rendering

## What this addresses

Rendering a large number of list or table rows can create slow render performance. Virtual scrolling renders the items in view rather than every item in the data set and can improve initial rendering for large lists.

## When to apply / when to skip
**Apply when:**
- Profiling identifies a large list or table as a rendering-performance problem.
- The list can render within a bounded scroll viewport.
- Rows have a consistent height, or the selected virtual-scroll implementation supports the row-height behavior required by the UI.
- Item identity can be tracked consistently.

**Skip when:**
- Measurement does not show the list or table is contributing to the observed performance problem.
- The result set is small enough that rendering it is not a measured problem.
- The delay is caused by a different source, such as network requests or expensive client-side processing.

## Recommended approaches

### Virtualize a fixed-height list

Use a virtual-list implementation that renders the visible rows instead of mapping the entire data set into the DOM.

**Good:**

```javascript
export default async function decorate(block) {
  const rowHeight = 56;
  const viewport = document.createElement('div');
  const spacer = document.createElement('div');
  const rows = document.createElement('div');

  viewport.className = 'account-list__viewport';
  viewport.style.height = '70vh';
  viewport.style.overflowY = 'auto';

  spacer.className = 'account-list__spacer';
  rows.className = 'account-list__rows';
  rows.style.position = 'relative';

  viewport.append(spacer, rows);
  block.replaceChildren(viewport);

  const response = await fetch(block.dataset.endpoint);
  const { accounts } = await response.json();

  spacer.style.height = `${accounts.length * rowHeight}px`;

  function renderVisibleRows() {
    const first = Math.floor(viewport.scrollTop / rowHeight);
    const visibleCount = Math.ceil(viewport.clientHeight / rowHeight) + 2;
    const last = Math.min(accounts.length, first + visibleCount);

    rows.replaceChildren();

    for (let index = first; index < last; index += 1) {
      const account = accounts[index];
      const row = document.createElement('div');
      const link = document.createElement('a');
      const close = document.createElement('button');

      row.className = 'account-list__item';
      row.dataset.accountId = account.id;
      row.style.position = 'absolute';
      row.style.top = `${index * rowHeight}px`;
      row.style.height = `${rowHeight}px`;

      link.href = account.path;
      link.textContent = account.title;

      close.type = 'button';
      close.textContent = 'Close';
      close.addEventListener('click', () => {
        block.dispatchEvent(new CustomEvent('accountclose', {
          bubbles: true,
          detail: { accountId: account.id },
        }));
      });

      row.append(link, close);
      rows.append(row);
    }
  }

  viewport.addEventListener('scroll', renderVisibleRows);
  renderVisibleRows();
}
```

For fixed-height rows, provide the row-size configuration required by the chosen implementation.

```javascript
export default function decorate(block) {
  const rowHeight = Number.parseInt(block.dataset.rowHeight, 10) || 48;

  block.classList.add('results-virtual-list');
  block.style.setProperty('--results-row-height', `${rowHeight}px`);

  const viewport = block.querySelector('.results-virtual-list__viewport');
  const rows = block.querySelectorAll('.results-virtual-list__row');

  if (!viewport || !rows.length) return;

  rows.forEach((row) => {
    row.style.height = `${rowHeight}px`;
  });

  viewport.style.maxHeight = `${rowHeight * 10}px`;
  viewport.style.overflowY = 'auto';
}
```

Use a stable `trackBy` function or equivalent item key where the implementation supports one.

### Measure before choosing virtualization

Use profiling to determine whether the list is the cause of the performance issue before adding virtualization. In some cases, reusing unchanged list-item DOM and using event delegation can reduce unnecessary updates without virtualizing the list.

```javascript
export default function decorate(block) {
  const list = document.createElement('ul');
  const itemById = new Map();

  block.replaceChildren(list);

  block.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;

    const item = button.closest('li[data-todo-id]');
    if (!item) return;

    block.dispatchEvent(new CustomEvent('todoaction', {
      bubbles: true,
      detail: {
        action: button.dataset.action,
        todoId: item.dataset.todoId,
      },
    }));
  });

  function updateTodos(todos) {
    const nextItems = [];

    todos.forEach((todo) => {
      let item = itemById.get(todo.id);

      if (!item) {
        item = document.createElement('li');
        item.dataset.todoId = todo.id;

        const label = document.createElement('span');
        const toggle = document.createElement('button');
        const remove = document.createElement('button');

        label.className = 'todo-list__label';
        toggle.type = 'button';
        toggle.dataset.action = 'toggle';
        toggle.textContent = 'Toggle';
        remove.type = 'button';
        remove.dataset.action = 'remove';
        remove.textContent = 'Remove';

        item.append(label, toggle, remove);
        itemById.set(todo.id, item);
      }

      item.querySelector('.todo-list__label').textContent = todo.title;
      nextItems.push(item);
    });

    list.replaceChildren(...nextItems);
  }

  block.updateTodos = updateTodos;
}
```

## Anti-patterns

### Rendering every result before the user scrolls

```javascript
// Bad: creates a DOM node for every fetched result
export default function decorate(block) {
  void renderAllResults();

  async function renderAllResults() {
    const response = await fetch(block.dataset.endpoint);
    const { results } = await response.json();

    const list = document.createElement('ul');

    results.forEach((result) => {
      const item = document.createElement('li');
      const link = document.createElement('a');

      link.href = result.path;
      link.textContent = result.title;
      item.append(link);
      list.append(item);
    });

    block.replaceChildren(list);
  }
}
```

**Why this is bad:** For a large result set, every item is rendered even when most items are outside the visible area. The evidence identifies rendering extensive lists as a performance concern.

### Rendering every result as a row

```html
<!-- Bad: every result is emitted into the initial page DOM -->
<div class="cmp-results">
  <div class="cmp-results__row">
    <a href="/result-1">Result 1</a>
    <span>Description</span>
    <button>Save</button>
  </div>
  <!-- Additional rows -->
</div>
```

**Why this is bad:** A large table or list still renders every row rather than limiting rendering to the visible portion of the data set.

### Applying fixed-height virtualization to rows without a matching row height

```javascript
// Bad: rows are positioned using 56px even though their expanded content is taller.
export default async function decorate(block) {
  const rowHeight = 56;
  const viewport = document.createElement('div');
  const spacer = document.createElement('div');
  const rows = document.createElement('div');

  viewport.style.height = '500px';
  viewport.style.overflowY = 'auto';
  rows.style.position = 'relative';

  viewport.append(spacer, rows);
  block.replaceChildren(viewport);

  const response = await fetch(block.dataset.endpoint);
  const { results } = await response.json();

  spacer.style.height = `${results.length * rowHeight}px`;

  function renderVisibleRows() {
    const first = Math.floor(viewport.scrollTop / rowHeight);
    const visibleCount = Math.ceil(viewport.clientHeight / rowHeight) + 2;
    const last = Math.min(results.length, first + visibleCount);

    rows.replaceChildren();

    for (let index = first; index < last; index += 1) {
      const result = results[index];
      const row = document.createElement('article');
      const heading = document.createElement('h3');
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      const description = document.createElement('p');

      row.style.position = 'absolute';
      row.style.top = `${index * rowHeight}px`;
      row.style.height = `${rowHeight}px`;

      heading.textContent = result.title;
      summary.textContent = 'Details';
      description.textContent = result.longDescription;
      details.open = true;
      details.append(summary, description);
      row.append(heading, details);
      rows.append(row);
    }
  }

  viewport.addEventListener('scroll', renderVisibleRows);
  renderVisibleRows();
}
```

**Why this is bad:** Fixed-height virtual-scroll implementations require the configured row size to correspond to the height of each row.