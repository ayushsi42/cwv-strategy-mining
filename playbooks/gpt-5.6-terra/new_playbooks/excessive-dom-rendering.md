---
issue_type: excessive-dom-rendering
required_validation:
- stable_row_height_or_measurement_strategy_confirmed_when_required_by_the_virtualization_implementation
- row_tracking_strategy_confirmed
forbidden_techniques: []
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
source_prs:
- shapeshift/web#11630
- greedy-team/react-todo-list#24
- ethereum/ethereum-org-website#17912
- mui/mui-x#22123
- NextCenturyCorporation/itm-evaluation-dashboard#513
- hirosystems/stacks-wallet-web#2078
- input-output-hk/daedalus#2924
- openline-ai/openline-customer-os#2427
- ant-design/ant-design#44349
- rango-exchange/rango-client#474
- woowacourse/perf-basecamp#142
- bitwarden/clients#10113
---
# Excessive DOM rendering

## What this addresses

For extensive lists, rendering every item can become a performance concern. The evidence PRs replace all-item rendering with virtualized lists or tables that render items in view. One implementation reports substantially faster initial rendering when many account items are present.

## When to apply / when to skip
**Apply when:**
- A list or table with many items has an observed rendering or scrolling performance problem.
- The selected virtualization implementation supports the required list behavior.
- Row sizing requirements are understood. For example, the Angular CDK virtual-scrolling implementation shown in the evidence requires a row size corresponding to each row's height.
- The framework or virtualizer can track rendered rows appropriately, such as Angular's `trackBy`.

## Recommended approaches

### Use a virtualized list or table for large datasets

The evidence includes implementations using:

- `react-virtuoso` for account and swap-history lists.
- `react-virtualized` with `react-table` for a stake-pool table.
- Angular CDK `*cdkVirtualFor` within a virtual-scroll viewport.
- Ant Design's `virtual` table support.

For example, the account-switch implementation replaces mapping every account with a `Virtuoso` component:

```tsx
import { Virtuoso } from 'react-virtuoso';

export function AccountList({ accounts, handleClose }) {
  return (
    <Virtuoso
      style={{ height: '70vh' }}
      totalCount={accounts.length}
      itemContent={(index) => (
        <AccountListItem
          handleClose={handleClose}
          account={accounts[index]}
        />
      )}
    />
  );
}
```

The evidence describes this approach as rendering list items in view rather than rendering the complete account list initially.

### Use the virtualizer supported by the existing UI stack

The evidence shows several approaches rather than one universal library:

- Use existing virtualization dependencies when they meet the required behavior.
- Consider grouping support when grouped list history is required.
- Import components individually when a dependency's tree-shaking behavior requires it, rather than assuming barrel imports will be removed from the bundle.

### Provide row sizing where the virtualizer requires it

The Angular virtual-table implementation uses a virtual-scroll viewport with an `itemSize` derived from `rowSize`:

```html
<cdk-virtual-scroll-viewport
  scrollWindow
  [itemSize]="rowSize"
>
  <table>
    <tbody>
      <tr *cdkVirtualFor="let row of rows$; trackBy: trackBy">
        <ng-container
          *ngTemplateOutlet="rowDef.template; context: { $implicit: row }"
        ></ng-container>
      </tr>
    </tbody>
  </table>
</cdk-virtual-scroll-viewport>
```

The associated documentation notes that this implementation requires a `rowSize` corresponding to the height of each row.

### Track rows when the framework supports it

The Angular implementation supplies a `trackBy` function to `*cdkVirtualFor`:

```html
<tr *cdkVirtualFor="let row of rows$; trackBy: trackBy" bitRow>
```

Use the tracking mechanism provided by the selected framework or virtualizer when rendering virtualized rows.

## Anti-patterns

### Mapping every result into DOM nodes

```javascript
// Bad — every result is rendered before the user scrolls
results.forEach((result) => {
  const row = document.createElement('article');
  row.className = 'search-result';

  row.innerHTML = `
    <a href="${result.path}">
      <img src="${result.thumbnail}" alt="">
      <h3>${result.title}</h3>
      <button type="button">Save</button>
    </a>
  `;

  document.querySelector('.search-results').append(row);
});
```

**Why this is bad:** The evidence identifies rendering extensive lists in full as a performance concern. The corresponding improvements replace complete-list rendering with virtualization that renders items in view.

### Rendering every account with a direct map

```tsx
// Bad — every account item is rendered immediately
export function AccountList({ accounts, handleClose }) {
  return (
    <>
      {accounts.map((account) => (
        <AccountListItem
          key={account.address}
          handleClose={handleClose}
          account={account}
        />
      ))}
    </>
  );
}
```

**Why this is bad:** The account-switch evidence describes a delay that grows with the number of accounts and replaces this full-list render with `react-virtuoso`.

### Using a non-virtualized table for a slow large table

```tsx
// Bad — every table row is rendered at once
<tbody>
  {rows.map((row) => (
    <tr key={row.id}>
      <td>{row.name}</td>
      <td>{row.status}</td>
    </tr>
  ))}
</tbody>
```

**Why this is bad:** The stake-pool and table evidence replaces slow table rendering with `react-virtualized`, `react-table`, or a virtual-table implementation.