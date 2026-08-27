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

```tsx
import React, { memo } from 'react';
import { Virtuoso } from 'react-virtuoso';

type Account = {
  address: string;
  name: string;
};

type AccountListProps = {
  accounts: Account[];
  onSelectAccount: (address: string) => void;
};

const AccountRow = memo(function AccountRow({
  account,
  onSelectAccount,
}: {
  account: Account;
  onSelectAccount: (address: string) => void;
}) {
  return (
    <button type="button" onClick={() => onSelectAccount(account.address)}>
      {account.name}
    </button>
  );
});

export function AccountList({ accounts, onSelectAccount }: AccountListProps) {
  return (
    <Virtuoso
      style={{ height: '70vh' }}
      totalCount={accounts.length}
      itemContent={(index) => (
        <AccountRow
          account={accounts[index]}
          onSelectAccount={onSelectAccount}
        />
      )}
    />
  );
}
```

This works because the browser only has to mount and paint the rows in or near the viewport, instead of every item in the dataset.

### Keep row rendering stable and memoized

When the parent re-renders, avoid forcing every visible row to re-render unless its own data changed.

```tsx
import React, { memo, useCallback } from 'react';

type Todo = {
  id: number;
  text: string;
  checked: boolean;
};

const TodoRow = memo(function TodoRow({
  todo,
  onToggle,
  onRemove,
}: {
  todo: Todo;
  onToggle: (id: number) => void;
  onRemove: (id: number) => void;
}) {
  const handleToggle = useCallback(() => onToggle(todo.id), [onToggle, todo.id]);
  const handleRemove = useCallback(() => onRemove(todo.id), [onRemove, todo.id]);

  return (
    <li>
      <label>
        <input type="checkbox" checked={todo.checked} onChange={handleToggle} />
        {todo.text}
      </label>
      <button type="button" onClick={handleRemove}>
        Remove
      </button>
    </li>
  );
});
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

```tsx
// Bad
export function AccountList({ accounts, onSelectAccount }) {
  return (
    <ul>
      {accounts.map((account) => (
        <li key={account.address}>
          <button type="button" onClick={() => onSelectAccount(account.address)}>
            {account.name}
          </button>
        </li>
      ))}
    </ul>
  );
}
```

**Why this is bad:** Every item mounts, lays out, and paints up front, so the cost grows with list size and can hurt interaction responsiveness.

### Virtualizing without a known row extent

```tsx
// Bad
<Virtuoso
  totalCount={items.length}
  itemContent={(index) => <Row item={items[index]} />}
/>
```

**Why this is bad:** If the virtualization strategy cannot estimate or measure row height reliably, scroll position and visible item calculation can become unstable, causing jank or incorrect rendering.

### Keeping the full list in the DOM and hiding most rows with CSS

```tsx
// Bad
<ul>
  {items.map((item, index) => (
    <li key={item.id} style={{ display: index > 20 ? 'none' : 'block' }}>
      {item.label}
    </li>
  ))}
</ul>
```

**Why this is bad:** Hidden nodes still cost memory and can still participate in layout work, so the DOM remains oversized even though the user only sees a subset.

### Recreating row callbacks for every item on every render

```tsx
// Bad
{todos.map((todo) => (
  <TodoRow
    key={todo.id}
    todo={todo}
    onToggle={() => toggleTodo(todo.id)}
    onRemove={() => removeTodo(todo.id)}
  />
))}
```

**Why this is bad:** New function identities can defeat memoization and cause avoidable row re-renders, which compounds the cost of large lists.

## Flavor-specific notes

### CS

Prefer a design-system or app-level virtualized table/list component when the page already uses one. If the list is inside an AEM component, keep the virtualization boundary in the client component and avoid pushing row iteration into HTL when the data is meant to be interactive.

### AMS

If the list is rendered through a JSP/HTL-backed component, confirm the row height and scroll container before switching to virtualization. Legacy table markup and sticky headers often need a dedicated virtualized wrapper rather than a direct `table > tbody > tr` loop.

### Headless

This issue is most common in client-rendered app shells and dashboards. Virtualization is usually the right fix when the list is large and interactive, but validate keyboard navigation, focus retention, and empty/loading states after the change.