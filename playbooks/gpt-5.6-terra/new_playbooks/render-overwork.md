---
issue_type: render-overwork
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: high
required_validation:
- Profile relevant render and state-update behavior before and after the change.
- Map subscription consumers and selector dependencies for the affected interaction.
- Verify selector result identity and run regression coverage for affected interaction
  states.
forbidden_techniques: []
source_prs:
- selfagency/stately#14
- AudiusProject/audius-client#1975
- mui/mui-x#15627
- mui/base-ui#1961
---
# Render overwork

> **Risk tier:** unverified · **CWV metric:** interaction responsiveness

## What this addresses

Broad client-state subscriptions can cause components to re-render or run derived calculations for updates they do not display. Evidence from state-management and component-library changes shows that using more selective subscriptions, selectors, and equality checks can reduce unnecessary re-renders.

This is a recommendation-only issue: subscription ownership, selector memoization, and state-update semantics are architecture-sensitive and require profiler evidence plus interaction regression testing.

## When to apply / when to skip
**Apply when:**
- A profiler shows repeated rendering, selector work, or DOM updates after a state update.
- The affected component subscribes to an entire store, a large state branch, or a derived object whose identity changes on unrelated updates.
- The state-update path, subscription consumers, and the selector's required fields are mapped.
- The owning team can profile the before-and-after interaction and run regression coverage for the affected UI states.

**Do not apply when:**
- The performance finding is not attributed to rendering or client-state propagation.
- The component genuinely needs every field in the subscribed state branch.
- The proposed selector returns a newly allocated array or object on every update without memoization or a suitable equality check.
- Moving subscription ownership would change loading, authorization, editing, analytics, or error-state behavior.
- The delivery code is third-party, generated, or lacks an identified application owner for regression testing.

## Recommended approaches

### Subscribe to the smallest stable state slice

Keep the broad state store available to the feature, but subscribe each interactive element only to the primitive values or stable entity references it renders. Selector-based subscriptions with an equality function can avoid notifying a subscriber when its selected value is unchanged.

**Good — subscription scoped to one product's saved state**

```javascript
// Illustrative store API
import { getPageStore } from '../../scripts/state/page-store.js';

export default function decorate(block) {
  const store = getPageStore();
  const productId = block.dataset.productId;
  const saveButton = block.querySelector('.product-card-save');

  const updateSavedState = (isSaved) => {
    block.classList.toggle('is-saved', isSaved);
    saveButton.setAttribute('aria-pressed', String(isSaved));
  };

  store.subscribe(
    (state) => state.savedProductIds.includes(productId),
    updateSavedState,
    Object.is,
  );

  updateSavedState(store.getState().savedProductIds.includes(productId));
}
```

The selector returns a boolean, so an equality check such as `Object.is` can distinguish unchanged and changed selected values.

### Keep interactive state scoped to the component that consumes it

Where a page contains multiple independent interactive features, keep each feature's subscription focused on the state it renders rather than using one update callback to redraw all features.

**Good — component-scoped saved-state subscription**

```javascript
// Illustrative store API
document.querySelectorAll('.product-card').forEach((card) => {
  const productId = card.dataset.productId;
  const button = card.querySelector('.product-card-save');
  const store = window.siteStores.getSavedProductsStore();

  store.subscribe(
    (state) => state.byProductId[productId] === true,
    (saved) => {
      button.setAttribute('aria-pressed', String(saved));
      card.classList.toggle('is-saved', saved);
    },
    Object.is,
  );
});
```

This pattern limits the selected value for each card to its saved state.

### Memoize derived collections and preserve selector result identity

For a list whose displayed items are derived from several state branches, create a named selector that preserves its result when its inputs have not changed. Profile the selector during the target interaction before changing it.

**Good — memoized selector for a derived search-results collection**

```javascript
// Illustrative store API
import { getSearchStore } from '../../scripts/state/search-store.js';

const visibleResultsSelector = (() => {
  let previousItems;
  let previousQuery;
  let previousResult;

  return (state) => {
    if (state.items === previousItems && state.query === previousQuery) {
      return previousResult;
    }

    previousItems = state.items;
    previousQuery = state.query;

    const query = state.query.trim().toLowerCase();
    previousResult = query
      ? state.items.filter((item) => item.title.toLowerCase().includes(query))
      : state.items;

    return previousResult;
  };
})();

export default function decorate(block) {
  const store = getSearchStore();

  const renderResults = (items) => {
    block.replaceChildren(...items.map((item) => {
      const link = document.createElement('a');
      link.href = item.path;
      link.textContent = item.title;
      return link;
    }));
  };

  store.subscribe(visibleResultsSelector, renderResults, Object.is);
  renderResults(visibleResultsSelector(store.getState()));
}
```

When the selector receives the same item collection and query references, this implementation returns the prior array reference. An equality check can then avoid a list update for that unchanged result.

## Anti-patterns

### Subscribe a block to the entire page store

```javascript
// Bad — blocks/product-card/product-card.js
import { getPageStore } from '../../scripts/state/page-store.js';

export default function decorate(block) {
  const store = getPageStore();

  store.subscribe((state) => {
    block.querySelector('.product-card-title').textContent = state.product.title;
    block.querySelector('.product-card-save').setAttribute(
      'aria-pressed',
      String(state.savedProductIds.includes(block.dataset.productId)),
    );
  });
}
```

**Why this is bad:** If this subscription runs for every page-store update, it can perform DOM work for updates that do not affect the product card.

### Return a new derived object from every subscription check

```javascript
// Bad — clientlib-search/search-results.js
searchStore.subscribe(
  (state) => ({
    query: state.query,
    results: state.items.filter((item) =>
      item.title.toLowerCase().includes(state.query.toLowerCase()),
    ),
  }),
  ({ results }) => renderResults(results),
  Object.is,
);
```

**Why this is bad:** The selector creates a new object and array on each evaluation. With reference equality, the result is treated as changed even when the displayed results are equivalent.