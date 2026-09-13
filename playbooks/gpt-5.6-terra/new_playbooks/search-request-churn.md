---
issue_type: search-request-churn
required_validation:
- search_component_scope_known
- search_endpoint_contract_confirmed
- search_ux_delay_approved
- search_result_rendering_path_known
forbidden_techniques: []
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
source_prs:
- psimaron/NewStory#2
- beyondessential/tupaia#4458
- BetterSocial/mobileapp#1996
- SJSUCSClub/acm-website-server#143
- redhat-developer/rhdh-plugins#882
---
# Search request churn

## What this addresses

Autocomplete and live-search controls that request results on every keystroke can create unnecessary network and backend work. Debouncing input reduces the number of requests made during rapid typing.

## When to apply / when to skip
**Apply when:**
- A search, autocomplete, GIF picker, product finder, or similar control sends a request for each input event
- The endpoint supports partial-query search
- The component can safely delay requests by a UX-approved interval, such as 200–300 ms
- The request path and result-rendering code are known, including how loading, empty, and error states are displayed

## Recommended approaches

### Debounce search requests

Keep the text field value updated immediately, but defer the search request until typing pauses.

```javascript
// Good — clientlib-site-search/js/site-search.js
(() => {
  const DEBOUNCE_MS = 300;

  const debounce = (callback, wait) => {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback(...args), wait);
    };
  };

  document.querySelectorAll('[data-site-search]').forEach((search) => {
    const input = search.querySelector('[data-search-input]');
    const results = search.querySelector('[data-search-results]');
    const status = search.querySelector('[data-search-status]');
    const endpoint = search.dataset.searchEndpoint;

    const renderResults = (items) => {
      results.replaceChildren(...items.map((item) => {
        const link = document.createElement('a');
        link.href = item.url;
        link.textContent = item.title;
        return link;
      }));
    };

    const requestResults = async (query) => {
      status.textContent = 'Searching…';

      try {
        const response = await fetch(
          `${endpoint}?q=${encodeURIComponent(query)}`,
          { headers: { Accept: 'application/json' } },
        );
        const payload = await response.json();

        renderResults(payload.results);
        status.textContent = `${payload.results.length} results`;
      } catch (error) {
        status.textContent = 'Search is temporarily unavailable.';
      }
    };

    input.addEventListener('input', debounce((event) => {
      requestResults(event.target.value.trim());
    }, DEBOUNCE_MS));
  });
})();
```

A 200–300 ms debounce can collapse rapid keystrokes into fewer requests. The evidence includes implementations using 200 ms and 300 ms debounce delays.

Use an appropriately scoped debounce utility. The evidence includes both a local debounce implementation and `lodash.debounce`; importing a focused debounce package instead of the full `lodash` package was specifically raised as a bundle-size consideration.

## Anti-patterns

### Fetching on every input event

```javascript
// Bad — one request is sent for every keystroke
input.addEventListener('input', (event) => {
  fetch(`/bin/site/search?q=${encodeURIComponent(event.target.value)}`)
    .then((response) => response.json())
    .then(renderResults);
});
```

**Why this is bad:** Typing a query such as “test” can send four requests, increasing network and backend load.

### Searching without debouncing

```javascript
// Bad — each input change immediately starts a search
input.addEventListener('input', () => {
  fetch(`/bin/site/search?q=${encodeURIComponent(input.value.trim())}`)
    .then((response) => response.json())
    .then(renderResults);
});
```

**Why this is bad:** Rapid typing can trigger multiple search requests. Debouncing delays the search update until typing pauses and reduces request volume during fast input.