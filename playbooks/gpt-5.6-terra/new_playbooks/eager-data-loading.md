---
issue_type: eager-data-loading
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: high
required_validation: []
forbidden_techniques: []
source_prs:
- galaxyproject/galaxy#13477
- Neogasogaeseo/Naega-Web#300
- kodadot/nft-gallery#5429
- Final-Project-Team11/Meer_catlender_FE#176
- okp4/dataverse-portal#199
- lightdash/lightdash#14182
- tutti-tutti/tutti-client#225
---
# Eager data loading

## What this addresses

Several source PRs replace complete or larger result loading with paged or lazy loading:

- Galaxy enables infinite scrolling and pagination for history and collection items, using page sizes of 500 history items and 100 collection elements.
- Lightdash lazy-loads ordinary table results on scroll, while retaining complete loading for pivot tables and tables with subtotals.
- Tutti applies cursor-based infinite loading for products and prefetches data before the scroll threshold; its PR reports LCP changing from 1.59 seconds to 0.97 seconds.
- Neoga introduces paginated notification loading with a page size of 15.
- KodaDot adjusts its infinite-scroll list configuration and increases its initial item count from 20 to 40.

## When to apply / when to skip
**Apply when:**
- The API provides a page, offset, or cursor parameter for retrieving later results.
- The interface can load additional items in response to scrolling or an explicit control.
- The list has filtering or other result-state requirements that can be preserved across page requests.

**Skip when:**
- The view requires all rows for its behavior. Lightdash retains complete loading for pivot tables and tables showing subtotals.

## Recommended approaches

### Load later pages as the visitor approaches the end of the loaded list

Use the API’s page or cursor contract to retrieve later results rather than treating the initial request as the only result request.

Galaxy uses pagination for history and collection items, and its collection drilldown uses pagination at every depth level. Tutti uses an infinite query with cursor-based product-page requests and prefetches product data before the user reaches the configured scroll threshold.

```javascript
async function fetchPage(cursor) {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);

  const response = await fetch(`/api/products?${params}`);
  if (!response.ok) throw new Error('Unable to load products');

  return response.json();
}
```

### Preserve filters and result mode when loading subsequent pages

The Dataverse PR combines infinite scrolling with `byType` filters. Subsequent requests should retain the active filter and other result state required by the API contract.

### Retain complete loading for modes that require all rows

Lightdash lazy-loads results on scroll for ordinary tables, but loads all pages when a table is pivoted or displays subtotals.

```javascript
async function loadResults({ cursor, mode }) {
  const requiresAllRows = ['pivot', 'subtotal'].includes(mode);

  const url = new URL('/api/results', window.location.origin);
  if (!requiresAllRows && cursor) {
    url.searchParams.set('cursor', cursor);
  }

  const response = await fetch(url);
  if (!response.ok) throw new Error('Results request failed');

  return response.json();
}
```

## Anti-patterns

### Using lazy loading for a table mode that requires all rows

**Why this is bad:** Lightdash explicitly retains complete loading for pivot tables and tables with subtotals rather than applying its ordinary scroll-based lazy-loading behavior to those modes.

### Loading later pages without preserving the active filter

**Why this is bad:** The Dataverse implementation includes both infinite scrolling and `byType` filtering. Later-page requests need to remain consistent with the active filter.

## Flavor-specific notes

### EDS

No EDS-specific implementation evidence is provided.

### CS

No CS-specific implementation evidence is provided.

### AMS

No AMS-specific implementation evidence is provided.

### Headless

Use the pagination contract exposed by the consuming API. The source PRs demonstrate cursor- and page-based approaches, including cursor-based product loading and page-based notification loading.