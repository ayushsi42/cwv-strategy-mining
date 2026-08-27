---
issue_type: dom-overrendering
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- greedy-team/react-todo-list#24
- NextCenturyCorporation/itm-evaluation-dashboard#513
- hirosystems/stacks-wallet-web#2078
- input-output-hk/daedalus#2924
- razorpay/blade#1075
- ant-design/ant-design#44349
- rango-exchange/rango-client#474
- bitwarden/clients#10113
- WawasCode/adh-app#52
---
# DOM overrendering

> **Risk tier:** medium · **Applies to:** CS, AMS, HEADLESS · **CWV metric:** INP, LCP

## What this addresses

Rendering every row in a large list or table at once creates unnecessary DOM, layout, and paint work. Virtualizing the list keeps only the visible rows mounted, which can reduce initial render cost and make scrolling and selection more responsive.

## When to apply / when to skip
**Apply when:**
- The UI renders a long, scrollable list or table with many repeated rows
- Profiling shows render time, layout, or paint cost growing with item count
- The row height is fixed or can be approximated well enough for virtualization
- The component owns the row rendering logic and can switch to a virtualized viewport safely

**Skip when:**
- The list is short enough that virtualization adds more complexity than benefit
- Rows have highly variable height and the virtualization strategy cannot measure them reliably
- The UI depends on full DOM presence for print, in-page search, or native table semantics that would be broken by virtualization
- The list is primarily server-rendered static content rather than interactive client rendering

## Recommended approaches

### Virtualize the row viewport

Render only the visible rows inside a virtualized scroller, and keep the row component focused on a single item.

```html
<!-- Good: virtualized list in an AEM client component -->
<div class="account-list" data-sly-use.model="com.example.components.AccountListModel">
  <div class="account-list__viewport" data-account-list>
    <template data-account-row-template>
      <button type="button" class="account-list__row">
        <span class="account-list__name"></span>
      </button>
    </template>
  </div>
</div>
```

```js
import { decorate } from './account-list.js';

export default function decorate(block) {
  const viewport = block.querySelector('[data-account-list]');
  const template = block.querySelector('[data-account-row-template]');
  const accounts = window.accountListData || [];

  if (!viewport || !template) return;

  const rowHeight = 56;
  const overscan = 6;
  const spacer = document.createElement('div');
  const rows = document.createElement('div');

  spacer.style.height = `${accounts.length * rowHeight}px`;
  rows.style.position = 'absolute';
  rows.style.left = '0';
  rows.style.right = '0';

  viewport.style.position = 'relative';
  viewport.style.overflowY = 'auto';
  viewport.style.height = '70vh';
  viewport.append(spacer, rows);

  function render() {
    const scrollTop = viewport.scrollTop;
    const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const end = Math.min(
      accounts.length,
      Math.ceil((scrollTop + viewport.clientHeight) / rowHeight) + overscan,
    );

    rows.innerHTML = '';
    rows.style.transform = `translateY(${start * rowHeight}px)`;

    for (let i = start; i < end; i += 1) {
      const account = accounts[i];
      const row = template.content.firstElementChild.cloneNode(true);
      row.querySelector('.account-list__name').textContent = account.name;
      row.addEventListener('click', () => window.onSelectAccount(account.address));
      rows.append(row);
    }
  }

  viewport.addEventListener('scroll', render, { passive: true });
  render();
}
```

This works because the browser only has to mount and paint the rows in or near the viewport, instead of every item in the dataset.

### Keep row rendering stable and memoized

When the parent re-renders, avoid forcing every visible row to re-render unless its own data changed.

```html
<!-- Good: stable row template with event delegation -->
<ul class="todo-list" data-todo-list>
  <li class="todo-list__item" data-todo-id="">
    <label>
      <input type="checkbox" data-todo-toggle />
      <span data-todo-text></span>
    </label>
    <button type="button" data-todo-remove>Remove</button>
  </li>
</ul>
```

```js
export default function decorate(block) {
  const list = block.querySelector('[data-todo-list]');
  if (!list) return;

  list.addEventListener('click', (event) => {
    const removeButton = event.target.closest('[data-todo-remove]');
    if (removeButton) {
      const item = removeButton.closest('[data-todo-id]');
      if (item) window.removeTodo(Number(item.dataset.todoId));
    }
  });

  list.addEventListener('change', (event) => {
    const toggle = event.target.closest('[data-todo-toggle]');
    if (toggle) {
      const item = toggle.closest('[data-todo-id]');
      if (item) window.toggleTodo(Number(item.dataset.todoId));
    }
  });
}
```

Memoization does not replace virtualization, but it reduces churn among the rows that remain mounted.

### Use a dedicated virtual table component when the library provides one

If the design system already exposes a virtualized table or list primitive, prefer that over hand-rolling scroll math.

```html
<!-- Good: table owns the viewport and row template -->
<bit-table-scroll [dataSource]="rows" [rowSize]="56">
  <ng-template bitRowDef let-row>
    <td bitCell>{{ row.name }}</td>
    <td bitCell>{{ row.status }}</td>
  </ng-template>
</bit-table-scroll>
```

A purpose-built component keeps the virtualization contract in one place and reduces the chance of inconsistent scroll behavior across screens.

## Anti-patterns

### Rendering every row with `map()` or `*ngFor` on large datasets

```html
<!-- Bad -->
<ul>
  <li data-sly-list.account="${accounts}">
    <button type="button" data-account-address="${account.address}">
      ${account.name}
    </button>
  </li>
</ul>
```

**Why this is bad:** Every item mounts, lays out, and paints up front, so the cost grows with list size and can hurt interaction responsiveness.

### Virtualizing without a known row extent

```js
// Bad
export default function decorate(block) {
  const items = window.items || [];
  const viewport = block.querySelector('[data-list]');
  if (!viewport) return;

  // Missing row height/measurement strategy makes scroll math unstable.
  items.forEach((item) => {
    const row = document.createElement('div');
    row.textContent = item.label;
    viewport.append(row);
  });
}
```

**Why this is bad:** If the virtualization strategy cannot estimate or measure row height reliably, scroll position and visible item calculation can become unstable, causing jank or incorrect rendering.

### Keeping the full list in the DOM and hiding most rows with CSS

```html
<!-- Bad -->
<ul>
  <li data-sly-list.item="${items}" class="${itemList.index > 20 ? 'is-hidden' : ''}">
    ${item.label}
  </li>
</ul>
```

**Why this is bad:** Hidden nodes still cost memory and can still participate in layout work, so the DOM remains oversized even though the user only sees a subset.

### Recreating row callbacks for every item on every render

```js
// Bad
export default function decorate(block) {
  const todos = window.todos || [];
  const list = block.querySelector('[data-todo-list]');
  if (!list) return;

  todos.forEach((todo) => {
    const row = document.createElement('div');
    row.textContent = todo.text;
    row.addEventListener('click', () => toggleTodo(todo.id));
    row.addEventListener('click', () => removeTodo(todo.id));
    list.append(row);
  });
}
```

**Why this is bad:** New function identities can defeat memoization and cause avoidable row re-renders, which compounds the cost of large lists.

## Flavor-specific notes

### CS

Prefer a design-system or app-level virtualized table/list component when the page already uses one. If the list is inside an AEM component, keep the virtualization boundary in the client component and avoid pushing row iteration into HTL when the data is meant to be interactive.

### AMS

If the list is rendered through a JSP/HTL-backed component, confirm the row height and scroll container before switching to virtualization. Legacy table markup and sticky headers often need a dedicated virtualized wrapper rather than a direct `table > tbody > tr` loop.

### Headless

This issue is most common in client-rendered app shells and dashboards. Virtualization is usually the right fix when the list is large and interactive, but validate keyboard navigation, focus retention, and empty/loading states after the change.