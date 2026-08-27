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

```tsx
// Good: subscribe to a narrow derived value
import { useSelector } from 'react-redux';

function SelectedCountBadge() {
  const selectedCount = useSelector((state) => state.selection.ids.length);

  return <span>{selectedCount}</span>;
}
```

This avoids rerendering the component for unrelated store updates. If the component only needs a count, do not subscribe to the whole selection object.

### Derive filtered data in a memoized selector

If the component needs a list, derive it from the store with a selector that only changes when the relevant inputs change.

```tsx
// Good: derive the visible collection list from the minimum inputs
import { useMemo } from 'react';
import { useSelector } from 'react-redux';

function VisibleItems({ filterValue }: { filterValue: string }) {
  const items = useSelector((state) => state.items.byId);
  const ids = useSelector((state) => state.items.visibleIds);

  const visibleItems = useMemo(() => {
    const needle = filterValue.toLowerCase();
    return ids
      .map((id) => items[id])
      .filter((item) => item.name.toLowerCase().includes(needle));
  }, [ids, items, filterValue]);

  return <ItemList items={visibleItems} />;
}
```

This keeps the expensive filtering out of unrelated rerenders and makes the dependency boundary explicit.

### Split one broad subscription into focused selectors

If a component reads multiple unrelated fields, split them so each field can update independently.

```tsx
// Good: separate subscriptions for separate concerns
import { useSelector } from 'react-redux';

function Toolbar() {
  const isOpen = useSelector((state) => state.panel.isOpen);
  const activeId = useSelector((state) => state.selection.activeId);

  return (
    <div>
      <span>{isOpen ? 'Open' : 'Closed'}</span>
      <span>{activeId ?? 'None'}</span>
    </div>
  );
}
```

This reduces the chance that a large object identity change forces a rerender when only one field changed.

## Anti-patterns

### Subscribing to the whole store slice when only one field is needed

```tsx
// Bad
function SelectedCountBadge() {
  const selection = useSelector((state) => state.selection);

  return <span>{selection.ids.length}</span>;
}
```

**Why this is bad:** Any change inside `state.selection` can rerender the component even when the count is unchanged, creating avoidable work during interactions.

### Returning a new derived object on every render without memoization

```tsx
// Bad
function VisibleItems({ filterValue }: { filterValue: string }) {
  const items = useSelector((state) => state.items.byId);
  const ids = useSelector((state) => state.items.visibleIds);

  const visibleItems = ids.map((id) => items[id]).filter((item) =>
    item.name.toLowerCase().includes(filterValue.toLowerCase())
  );

  return <ItemList items={visibleItems} />;
}
```

**Why this is bad:** The derived array is recreated on every render, so downstream children may rerender even when the underlying inputs did not meaningfully change.

### Using a broad context value for selection state

```tsx
// Bad
const SelectionContext = React.createContext({ selection: {}, setSelection: () => {} });

function SelectionLabel() {
  const { selection } = React.useContext(SelectionContext);
  return <span>{selection.ids.length}</span>;
}
```

**Why this is bad:** Any provider value change can rerender all consumers, even those that only need a tiny part of the selection state.

### Triggering rerenders through side-effectful selection updates

```tsx
// Bad
function onSelect(id: string) {
  store.setState({
    selection: {
      ...store.getState().selection,
      activeId: id,
      allItems: store.getState().items,
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

  // Subscribe only to the value this block needs.
  // Replace this with the project's actual client-side store API.
  const unsubscribe = window.selectionStore?.subscribe?.(
    (state) => state.selection.ids.length,
    updateSelectedCount
  );

  return unsubscribe;
}
```

### CS

In React-based AEM CS frontends, prefer selectors that read only the fields needed by the component. If a page-level provider feeds many components, split the provider value or expose focused selectors so selection changes do not rerender the whole tree. For client libraries, define them in `.content.xml` rather than packaging them through `package.json` or webpack-specific metadata.

### AMS

For AMS client-rendered widgets, keep selection state local to the widget when possible. If a shared store is required, avoid passing the full store object through props or context; derive the smallest stable value before rendering the component subtree. For client libraries, use the AEM clientlib `.content.xml` structure instead of bundler-only configuration.

### Headless

Headless apps often have the highest risk of selection churn because the UI is entirely client-driven. Use memoized selectors and avoid broad subscriptions in list, filter, and toolbar components that update frequently during user interaction.