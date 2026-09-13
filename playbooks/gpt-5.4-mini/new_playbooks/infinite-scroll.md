---
issue_type: infinite-scroll
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
required_validation:
- viewport_triggered_loading_confirmed
- pagination_or_cursor_api_available
- no_keyboard_focus_trap_in_results
- loading_state_and_end_state_defined
- duplicate_fetch_guard_present
forbidden_techniques:
- pattern: \bwindow\.onscroll\s*=
  reason: Don't wire infinite loading to a raw scroll handler — it is noisy, hard
    to throttle correctly, and can hurt INP
- pattern: \baddEventListener\s*\(\s*["']scroll["']
  reason: Don't use unbounded scroll listeners for infinite loading — prefer IntersectionObserver
    to reduce main-thread work
- pattern: \bsetInterval\s*\(
  reason: Don't poll for more results — polling wastes CPU and can trigger repeated
    fetches
- pattern: \bfetch\s*\([^)]*\)\s*\.then\s*\([^)]*\)\s*=>\s*[^;]*append
  reason: Don't append results without a paging guard — duplicate requests and duplicate
    DOM nodes are common failure modes
- pattern: \binnerHTML\s*=
  reason: Don't rebuild the results list with innerHTML on every page load — it can
    blow away focus and increase layout work
source_prs:
- ampproject/amphtml#37360
- searxng/searxng#916
- kitspace/kitspace-v2#504
- skylark-platform/skylark-ui#22
- Alt-Org/Altzone-WebPages#499
---
# Infinite scroll

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** INP, LCP

## What this addresses

Infinite scroll loads the next page when the user approaches the end of the current results, instead of waiting for an explicit click. Done well, it reduces interaction friction and can improve perceived responsiveness; done poorly, it can create repeated fetches, focus loss, and long main-thread tasks that hurt INP, and it can delay LCP on long result lists by continuously extending the initial render.

## When to apply / when to skip
**Apply when:**
- The page shows a paginated list or feed where loading more results on demand is a product requirement
- The next page can be fetched with a stable page/offset/cursor API
- The implementation can use a viewport sentinel or equivalent visibility trigger
- Loading, end-of-list, and error states are defined before emitting the fix

**Skip when:**
- The list is short enough that pagination is already sufficient
- The backend cannot provide deterministic paging or cursor semantics
- The UI must preserve a strict page boundary for accessibility, analytics, or legal reasons
- The page is primarily a search results page where explicit pagination is required for shareable state or deep-linking
- The implementation would require a broad refactor of focus management, virtualization, or server APIs beyond the scope of a safe code fix

## Recommended approaches

### Use IntersectionObserver with a sentinel element

```html
<!-- Good: results list with a sentinel at the end -->
<ul id="results">
  <li>Result 1</li>
  <li>Result 2</li>
  <li>Result 3</li>
</ul>

<div id="load-more-sentinel" aria-hidden="true"></div>
<div id="results-status" aria-live="polite"></div>
```

```js
// Good: load the next page when the sentinel enters the viewport
const sentinel = document.getElementById('load-more-sentinel');
const status = document.getElementById('results-status');
const results = document.getElementById('results');

let page = 1;
let loading = false;
let hasMore = true;

async function loadNextPage() {
  if (loading || !hasMore) return;
  loading = true;
  status.textContent = 'Loading more results…';

  try {
    const response = await fetch(`/api/results?page=${page + 1}`);
    const data = await response.json();

    if (!data.items.length) {
      hasMore = false;
      status.textContent = 'No more results';
      return;
    }

    page += 1;
    data.items.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = item.title;
      results.appendChild(li);
    });
    status.textContent = '';
  } finally {
    loading = false;
  }
}

const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting) {
    loadNextPage();
  }
}, { rootMargin: '200px' });

observer.observe(sentinel);
```

IntersectionObserver moves the trigger work off the scroll path and only fires when the sentinel is near view. The `loading` and `hasMore` guards prevent duplicate fetches and repeated DOM appends.

### Preserve focus and announce state changes

```html
<!-- Good: explicit status and stable focus target -->
<button id="load-more" type="button">Load more</button>
<div id="results-status" aria-live="polite"></div>
```

```js
function appendResults(items) {
  const list = document.getElementById('results');
  const fragment = document.createDocumentFragment();

  items.forEach((item) => {
    const li = document.createElement('li');
    const link = document.createElement('a');
    link.href = item.url;
    link.textContent = item.title;
    li.appendChild(link);
    fragment.appendChild(li);
  });

  list.appendChild(fragment);
  document.getElementById('results-status').textContent = `${items.length} more results loaded`;
}
```

A live region tells assistive tech that more content arrived, and appending via a fragment reduces layout churn. If the page includes interactive cards, keep the tab order stable and avoid replacing the whole list.

### Keep paging state in the URL or request key

```js
// Good: stable request key for page-based loading
const params = new URLSearchParams(location.search);
const category = params.get('category') || '';
const page = Number(params.get('page') || '1');

fetch(`/api/news?category=${encodeURIComponent(category)}&page=${page}&limit=20`);
```

Stable paging keys make retries, back/forward navigation, and cache behavior predictable. This is especially important when the list is also filterable or category-scoped.

## Anti-patterns

### Raw scroll handler for loading more

```js
// Bad
window.addEventListener('scroll', () => {
  if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
    loadNextPage();
  }
});
```

**Why this is bad:** Scroll events can fire continuously during user input, increasing main-thread work and making duplicate fetches more likely; IntersectionObserver is a better fit for viewport-driven loading.

### Replacing the whole list on every page load

```js
// Bad
fetch('/api/results?page=2')
  .then((r) => r.json())
  .then((data) => {
    const list = document.getElementById('results');
    const fragment = document.createDocumentFragment();

    data.items.forEach((item) => {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = item.title;
      li.appendChild(link);
      fragment.appendChild(li);
    });

    list.appendChild(fragment);
  });
```

**Why this is bad:** Rebuilding the list destroys existing DOM state, can drop keyboard focus, and increases layout and paint work instead of incrementally extending the list.

### Polling for more content

```js
// Bad
setInterval(() => {
  if (nearBottom()) {
    loadNextPage();
  }
}, 250);
```

**Why this is bad:** Polling wastes CPU even when the user is idle and can trigger repeated requests; viewport observation is event-driven and cheaper.

### Loading more without a duplicate-request guard

```js
// Bad
async function loadNextPage() {
  const data = await fetch('/api/results?page=2').then((r) => r.json());
  data.items.forEach(appendItem);
}
```

**Why this is bad:** Without `loading` and `hasMore` guards, the sentinel can trigger multiple times and append duplicate pages, which is a common source of jank and broken end-of-list behavior.

## Flavor-specific notes

### CS

Use the page component or HTL template to render a stable results container, a sentinel, and a status region. If the page is backed by a Sling model, expose the initial page size and the next-page endpoint from the model rather than hard-coding them in the client script.

```html
<!-- Good: HTL with a model-backed endpoint -->
<sly data-sly-use.model="com.example.core.models.SearchResultsModel" />

<ul id="results" data-endpoint="${model.endpoint}" data-page-size="${model.pageSize}">
  <sly data-sly-list.item="${model.initialItems}">
    <li><a href="${item.url}">${item.title}</a></li>
  </sly>
</ul>

<div id="load-more-sentinel" aria-hidden="true"></div>
<div id="results-status" aria-live="polite"></div>
```

If the page uses clientlibs, keep the infinite-scroll logic in a dedicated clientlib category and include it only on templates that need it.

### AMS

Prefer a JSP/HTL-backed results fragment with server-rendered initial items and a small client-side loader. Keep the paging contract explicit in the component output so the browser script does not infer URLs from DOM structure.

```xml
<!-- Good: clientlib category for the loader -->
<jcr:root
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.infinite-scroll]"
    dependencies="[site.base]"/>
```

```html
<!-- Good: component markup with a sentinel -->
<div class="results" data-endpoint="/bin/site/results" data-page-size="20">
  <ul id="results">
    <li><a href="/content/site/item-1.html">Item 1</a></li>
  </ul>
  <div id="load-more-sentinel" aria-hidden="true"></div>
  <div id="results-status" aria-live="polite"></div>
</div>
```

On AMS, verify the rendered output path before changing the component, because JSP include chains can alter the final DOM and break the sentinel placement.

### Headless

Infinite scroll is usually a client application concern in headless delivery. Implement it in the consuming app only when the API provides stable paging and the UI can preserve accessibility and navigation state.

```js
// Good: client app consumes a paged headless API
const res = await fetch(`/api/articles?limit=20&cursor=${cursor}`);
const { items, nextCursor } = await res.json();
```

If the headless frontend already virtualizes the list, prefer extending the virtualization strategy rather than layering infinite scroll on top of an unbounded DOM.