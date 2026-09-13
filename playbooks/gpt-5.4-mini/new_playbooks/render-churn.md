---
issue_type: render-churn
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- interaction_hot_path_confirmed
- broad_context_read_identified
- fine_grained_selector_available
- no_server_render_dependency
- no_existing_memoization_boundary
forbidden_techniques: []
source_prs:
- qbittorrent/qBittorrent#23752
- AudiusProject/audius-client#1975
- agritheory/stonecrop#137
- adobe/react-spectrum#6046
- mui/mui-x#15627
- ag-grid/ag-grid#10020
- mui/base-ui#1961
---
# Render churn

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** INP

## What this addresses

Broad context reads and coarse subscriptions can cause components to re-render more often than necessary during user interaction. Narrowing the read surface to finer-grained selectors or item-level subscriptions can reduce update fan-out, which may improve responsiveness and lower INP risk.

## When to apply / when to skip
**Apply when:**
- A component re-renders because it reads a large shared object, store, or context and only needs a small slice of it
- Interaction handlers trigger updates that fan out to many siblings or descendants
- The component is on a hot path such as selection, focus movement, table navigation, menus, or list item activation

**Skip when:**
- The component already uses a selector/subscription pattern that only updates on relevant state changes
- The render cost is not interaction-driven, or the issue is primarily network, layout, or paint bound
- The state is needed synchronously for server rendering or initial HTML generation, and changing the read path would alter output semantics
- The fix would require a broad architectural rewrite rather than a local subscription refinement

## Recommended approaches

### Read only the state slice you need

Prefer selectors or derived reads over consuming a whole context/store object. This keeps unrelated updates from re-rendering the component.

```ts
// Good: subscribe to only the selected row state
const isSelected = useStore((state) => state.selectedRowIds.has(rowId));
const isExpanded = useStore((state) => state.expandedRowIds.has(rowId));

return (
  <button
    aria-pressed={isSelected}
    aria-expanded={isExpanded}
    onClick={() => toggleRow(rowId)}
  >
    {label}
  </button>
);
```

This works because the component only re-renders when the selected values change, not when unrelated store fields update.

### Split broad context into item-level subscriptions

If a parent context currently exposes a large mutable map or object, expose a subscription API and let each item subscribe to its own key or derived value.

```ts
// Good: item-level subscription instead of reading the whole map
const value = useSyncExternalStore(
  subscribeToRow(rowId),
  () => getRowState(rowId),
  () => getRowState(rowId)
);

return <Row selected={value.selected} focused={value.focused} />;
```

This can reduce fan-out in large collections because each row updates independently.

### Derive stable props before passing them down

Compute the minimal primitive props needed by children so they do not depend on a large parent object.

```ts
// Good: pass primitives, not the whole table state
const canExpand = row.type === 'group' && row.children.length > 0;
const isActive = activeRowId === row.id;

return <TableRow canExpand={canExpand} isActive={isActive} />;
```

Smaller prop surfaces make memoization and equality checks more effective, especially in dense interactive lists.

## Anti-patterns

### Reading a broad context object in every item

```ts
// Bad
const tableData = useContext(TableDataContext);

return (
  <tr onClick={() => tableData.toggleRowExpand(rowIndex)}>
    <td>{tableData.display[rowIndex].isParent ? '+' : ''}</td>
  </tr>
);
```

**Why this is bad:** Every change to the shared context can re-render all consumers, even when only one row changed, which increases interaction work and can hurt INP.

### Recomputing item state from a large shared store on every render

```ts
// Bad
function Row({ rowIndex }) {
  const store = useContext(StoreContext);
  const selected = store.selectedRows.includes(store.rows[rowIndex].id);
  const expanded = store.expandedRows.includes(store.rows[rowIndex].id);

  return <RowView selected={selected} expanded={expanded} />;
}
```

**Why this is bad:** The component depends on the entire store object, so unrelated store updates can still trigger render work and duplicate derived-state computation.

### Using unstable keys or identity churn to force updates

```vue
<!-- Bad -->
<ARow
  v-for="(row, rowIndex) in tableData.rows"
  :key="row.id || v4()"
  :row="row"
  :rowIndex="rowIndex"
/>
```

**Why this is bad:** Unstable identity can cause remounts and extra render work instead of targeted updates, which makes interaction slower rather than faster.

## Flavor-specific notes

### EDS

Use block-local state and finer-grained selectors inside the block’s client-side code. If a block currently reads a large shared object from a module singleton, refactor to per-item subscriptions or derived primitives so only the affected block subtree updates.

```js
export default function decorate(block) {
  const rows = [...block.querySelectorAll('[data-row-id]')];

  rows.forEach((row) => {
    const rowId = row.dataset.rowId;
    const button = row.querySelector('button');

    button.addEventListener('click', () => {
      const isExpanded = row.getAttribute('aria-expanded') === 'true';
      row.setAttribute('aria-expanded', String(!isExpanded));
      row.classList.toggle('is-expanded', !isExpanded);
    });
  });
}
```

### CS

Prefer Sling Model or HTL output that emits stable primitives, then keep client-side interaction state in a narrow store or selector layer. Avoid passing the entire component model into every interactive child when only one or two fields are needed.

```html
<sly data-sly-use.model="com.example.components.TableModel" />
<table class="cmp-table">
  <tbody data-sly-list.row="${model.rows}">
    <tr data-row-id="${row.id}" aria-expanded="${row.expanded}">
      <td>
        <button
          type="button"
          class="cmp-table__toggle"
          data-row-id="${row.id}"
          aria-pressed="${row.selected}"
        >
          ${row.label}
        </button>
      </td>
    </tr>
  </tbody>
</table>
```

### AMS

When JSP or legacy component code exposes a large request-scoped object to many interactive widgets, narrow the data passed into each widget and avoid recomputing shared state in every render/update cycle.

```jsp
<%@ page session="false" %>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %>
<c:forEach var="row" items="${requestScope.tableRows}">
  <tr data-row-id="${row.id}" aria-expanded="${row.expanded}">
    <td>
      <button type="button" class="cmp-table__toggle" data-row-id="${row.id}">
        <c:out value="${row.label}" />
      </button>
    </td>
  </tr>
</c:forEach>
```

### Headless

Use selector-based client state for interactive shells and list views. Headless front ends often have large normalized stores; the fix is to subscribe to the smallest possible slice for each interactive component rather than reading the whole entity graph.