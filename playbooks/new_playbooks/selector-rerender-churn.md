---
issue_type: selector-rerender-churn
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- identify_broad_subscription_source
- confirm_selector_can_be_narrowed
- verify_no_state_semantics_change
- confirm_render_path_is_client_side
forbidden_techniques:
- pattern: (?:.*\buseSelector\s*\(\s*\(\s*state\s*\)\s*=>\s*state\.[A-Za-z0-9_]+\s*\))
  reason: Matches a known anti-pattern from the source evidence.
- pattern: (?:.*\bReact\.createContext\s*\(\s*\{\s*selection\s*:\s*\{\s*\}\s*,\s*setSelection\s*:\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}\s*\))
  reason: Matches a known anti-pattern from the source evidence.
source_prs:
- myparcelnl/delivery-options#281
- vercel/swr#1962
- AudiusProject/audius-client#1975
- aave/interface#964
- elastic/kibana#145234
- sveltejs/kit#13140
- mui/mui-x#15627
- mui/base-ui#1961
- hashicorp/nomad#12370
---
# Selector rerender churn

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** INP

## What this addresses

Broad store subscriptions can cause components to rerender when unrelated state changes, especially during selection or focus updates. Narrowing the subscription to the smallest stable slice reduces wasted render work and can help interaction responsiveness, which may improve INP and perceived smoothness.

## When to apply / when to skip

**Apply when:**
- A component rerenders on selection changes even though most of its props/state did not change
- A store hook or context subscription returns a large object when the component only needs a small derived value
- The rerender path is client-side and can be improved by selecting a narrower slice or memoized derivation
- The change preserves the same visible behavior and only reduces unnecessary rerenders

**Skip when:**
- The component already subscribes to the minimal state it needs
- The rerender is caused by a real UI state change that must repaint
- The fix would require changing business logic, data flow, or state ownership
- The component is server-rendered only and has no client-side subscription churn to optimize

## Recommended approaches

### Select the smallest stable slice

Prefer a selector that returns only the boolean, id, or derived list the component actually needs.

```js
// Good: subscribe to a narrow derived value in an EDS block
export default function decorate(block) {
  const selectedCountEl = block.querySelector('[data-selected-count]');
  if (!selectedCountEl) return;

  const render = (state) => {
    selectedCountEl.textContent = String(state.selection.ids.length);
  };

  render(window.selectionStore.getState());
  return window.selectionStore.subscribe((nextState) => {
    render(nextState);
  });
}
```

This avoids rerendering the component for unrelated store updates. If the component only needs a count, do not subscribe to the whole selection object.

### Derive filtered data in a memoized selector

If the component needs a list, derive it from the store with a selector that only changes when the relevant inputs change.

```js
// Good: derive the visible collection list from the minimum inputs in an EDS block
export default function decorate(block) {
  const listEl = block.querySelector('[data-visible-items]');
  const filterInput = block.querySelector('[data-filter-value]');
  if (!listEl || !filterInput || !window.itemsStore) return;

  const render = () => {
    const state = window.itemsStore.getState();
    const needle = filterInput.value.toLowerCase();
    const visibleItems = state.items.visibleIds
      .map((id) => state.items.byId[id])
      .filter((item) => item.name.toLowerCase().includes(needle));

    listEl.innerHTML = visibleItems
      .map((item) => `<li>${item.name}</li>`)
      .join('');
  };

  render();
  const unsubscribe = window.itemsStore.subscribe(render);
  filterInput.addEventListener('input', render);
  return () => {
    unsubscribe?.();
    filterInput.removeEventListener('input', render);
  };
}
```

This keeps the expensive filtering out of unrelated rerenders and makes the dependency boundary explicit.

### Split one broad subscription into focused selectors

If a component reads multiple unrelated fields, split them so each field can update independently.

```js
// Good: separate subscriptions for separate concerns in an EDS block
export default function decorate(block) {
  const statusEl = block.querySelector('[data-panel-status]');
  const activeIdEl = block.querySelector('[data-active-id]');
  if (!statusEl || !activeIdEl || !window.selectionStore) return;

  const renderStatus = (state) => {
    statusEl.textContent = state.panel.isOpen ? 'Open' : 'Closed';
  };

  const renderActiveId = (state) => {
    activeIdEl.textContent = state.selection.activeId || 'None';
  };

  renderStatus(window.selectionStore.getState());
  renderActiveId(window.selectionStore.getState());

  const unsubscribe = window.selectionStore.subscribe((nextState) => {
    renderStatus(nextState);
    renderActiveId(nextState);
  });

  return unsubscribe;
}
```

This reduces the chance that a large object identity change forces a rerender when only one field changed.

## Anti-patterns

### Subscribing to the whole store slice when only one field is needed

```js
// Bad: subscribing to the whole selection slice in an EDS block
export default function decorate(block) {
  const selectedCountEl = block.querySelector('[data-selected-count]');
  if (!selectedCountEl || !window.selectionStore) return;

  const render = (state) => {
    selectedCountEl.textContent = String(state.selection.ids.length);
  };

  render(window.selectionStore.getState());
  return window.selectionStore.subscribe((nextState) => {
    render(nextState);
  });
}
```

**Why this is bad:** Any change inside `state.selection` can rerender the component even when the count is unchanged, creating avoidable work during interactions.

### Returning a new derived object on every render without memoization

```js
// Bad: recomputing the visible list on every client-side update in an EDS block
export default function decorate(block) {
  const listEl = block.querySelector('[data-visible-items]');
  const filterInput = block.querySelector('[data-filter-value]');
  if (!listEl || !filterInput || !window.itemsStore) return;

  const render = () => {
    const state = window.itemsStore.getState();
    const visibleItems = state.items.visibleIds
      .map((id) => state.items.byId[id])
      .filter((item) => item.name.toLowerCase().includes(filterInput.value.toLowerCase()));

    listEl.innerHTML = visibleItems
      .map((item) => `<li>${item.name}</li>`)
      .join('');
  };

  render();
  const unsubscribe = window.itemsStore.subscribe(render);
  filterInput.addEventListener('input', render);
  return () => {
    unsubscribe?.();
    filterInput.removeEventListener('input', render);
  };
}
```

**Why this is bad:** The derived array is recreated on every render, so downstream children may rerender even when the underlying inputs did not meaningfully change.

### Using a broad context value for selection state

```html
<!-- Bad: broad HTL output encourages consumers to depend on the whole selection object -->
<sly data-sly-use.model="com.example.components.SelectionModel" />
<div class="selection-context" data-selection='${model.selection @ context="attribute"}'>
  <span class="selection-context__count">${model.selection.ids.length}</span>
</div>
```

**Why this is bad:** Any provider value change can rerender all consumers, even those that only need a tiny part of the selection state.

### Triggering rerenders through side-effectful selection updates

```js
// Bad: copying unrelated data into selection state in an EDS client-side store update
function onSelect(id) {
  window.selectionStore.setState({
    selection: {
      ...window.selectionStore.getState().selection,
      activeId: id,
      allItems: window.itemsStore.getState().items,
    },
  });
}
```

**Why this is bad:** Copying unrelated data into the selection state expands the update surface and can make selection changes more expensive than they need to be.

## Flavor-specific notes

### EDS

Use block-local state or a narrow client-side store subscription inside the block rather than reading a large shared object in `decorate(block)`. If a block only needs the active item or selected index, subscribe to that value directly and keep the rest of the data outside the render path.

```js
// Good: EDS block decorator with a narrow client-side subscription
export default function decorate(block) {
  const selectedCountEl = block.querySelector('[data-selected-count]');
  const updateSelectedCount = (count) => {
    if (selectedCountEl) selectedCountEl.textContent = String(count);
  };

  const state = window.selectionStore?.getState?.();
  updateSelectedCount(state?.selection?.ids?.length ?? 0);

  const unsubscribe = window.selectionStore?.subscribe?.((nextState) => {
    updateSelectedCount(nextState.selection.ids.length);
  });

  return unsubscribe;
}
```

### CS

In AEM CS frontends, prefer HTL or clientlib-loaded vanilla JS that reads only the fields needed by the component. If a page-level model or client-side store feeds many components, split the data access so selection changes do not rerender the whole tree. For client libraries, define them in `.content.xml` and load them via categories/dependencies rather than bundler-only configuration.

```html
<!-- Good: HTL renders a narrow selection badge and clientlib handles updates -->
<sly data-sly-use.model="com.example.components.SelectionModel" />
<span class="selection-badge" data-selected-count="${model.selectedCount}">${model.selectedCount}</span>
```

```js
// Good: clientlib JS updates only the needed DOM node
(function () {
  const badge = document.querySelector('[data-selected-count]');
  if (!badge || !window.selectionStore) return;

  const render = (state) => {
    badge.textContent = String(state.selection.ids.length);
  };

  render(window.selectionStore.getState());
  window.selectionStore.subscribe(render);
})();
```

```xml
<!-- Good: clientlib definition -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.selection]"
    dependencies="[cq.jquery]" />
```

### AMS

For AMS client-rendered widgets, keep selection state local to the widget when possible. If a shared store is required, avoid passing the full store object through props or context; derive the smallest stable value before rendering the component subtree. For client libraries, use the AEM clientlib `.content.xml` structure instead of bundler-only configuration.

```html
<!-- Good: HTL outputs only the narrow value needed by the widget -->
<sly data-sly-use.model="com.example.components.SelectionModel" />
<div class="toolbar">
  <span class="toolbar__status">${model.isPanelOpen ? 'Open' : 'Closed'}</span>
  <span class="toolbar__active-id">${model.activeId ? model.activeId : 'None'}</span>
</div>
```

```js
// Good: client-side widget reads focused values only
(function () {
  const statusEl = document.querySelector('.toolbar__status');
  const activeIdEl = document.querySelector('.toolbar__active-id');
  if (!statusEl || !activeIdEl || !window.selectionStore) return;

  const render = (state) => {
    statusEl.textContent = state.panel.isOpen ? 'Open' : 'Closed';
    activeIdEl.textContent = state.selection.activeId || 'None';
  };

  render(window.selectionStore.getState());
  window.selectionStore.subscribe(render);
})();
```

### Headless

Headless apps often have the highest risk of selection churn because the UI is entirely client-driven. Use memoized selectors and avoid broad subscriptions in list, filter, and toolbar components that update frequently during user interaction.