---
issue_type: page-slice-rendering
applicable_flavors:
- cs
- ams
- headless
risk_tier: low
required_validation:
- list_view_has_client_side_rendering_bottleneck
- total_items_or_page_size_known
- pagination_state_can_be_preserved
- page_slice_does_not_break_sort_or_filter_semantics
forbidden_techniques:
- pattern: \ball\s+rows\b
  reason: Don't add an 'all rows' mode as the default fix — it defeats the purpose
    of slicing the rendered DOM
- pattern: limit\s*=\s*[-"]?1
  reason: Don't implement a hidden 'show all' sentinel in the UI path — it reintroduces
    the large-DOM rendering problem
- pattern: slice\s*\(\s*0\s*,\s*items\.length\s*\)
  reason: Don't keep rendering the full list and call it pagination — the DOM is still
    unbounded
- pattern: <a[^>]*href\s*=\s*["'][^"'>]*page=\{\{?\s*1\s*\}\}?[^"'>]*>
  reason: Don't hardcode pagination links without preserving the current filter/search
    state
source_prs:
- getarcaneapp/arcane#1547
- CDCgov/dibbs-ecr-refiner#665
- elastic/kibana#136588
- PostHog/posthog#11037
- manifoldmarkets/manifold#881
- ISPP-12/SarandONGa#617
- torchbox/torchbox.com#185
- CDCgov/prime-simplereport#8371
- awesome-academy/dn_oe61_nodejs-tran-van-duyet#3
---
# Page slice rendering

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** INP, LCP

## What this addresses

Large lists and tables can make the browser do too much work at once: more DOM nodes to layout, paint, and keep interactive. Paginating the list reduces the number of rows rendered per view, which lowers main-thread work and can improve INP and sometimes LCP on large listings.

## When to apply / when to skip
**Apply when:**
- A listing page renders many repeated rows/cards/items in the browser
- The page is slow because of DOM size, layout, or event-handler churn rather than data fetching alone
- The current view can be split into stable pages without changing the meaning of the list

**Skip when:**
- The list is already server-paginated and the browser only renders one page at a time
- The UI is virtualized already and only visible rows are mounted
- The page must support true infinite scroll instead of discrete pages
- Pagination would break a required sort/filter contract or hide critical context that must remain visible together

## Recommended approaches

### Server-side page slicing with preserved query state

Render only the current page of results, and keep filters/search/sort parameters in the pagination links.

```java
// Good: Sling Model-backed server pagination
package com.example.core.models;

import java.util.List;
import javax.annotation.PostConstruct;
import javax.inject.Inject;
import javax.inject.Named;

import org.apache.sling.api.SlingHttpServletRequest;
import org.apache.sling.models.annotations.Model;
import org.apache.sling.models.annotations.injectorspecific.RequestAttribute;

@Model(adaptables = SlingHttpServletRequest.class)
public class ProjectListModel {

    @Inject
    private ProjectService projectService;

    @RequestAttribute
    private String title;

    @RequestAttribute
    private String country;

    private List<Project> projects;
    private Page<Project> page;

    @PostConstruct
    protected void init() {
        int pageNumber = 1;
        int pageSize = 12;

        this.page = projectService.findProjects(pageNumber, pageSize, title, country);
        this.projects = page.getItems();
    }

    public List<Project> getProjects() {
        return projects;
    }

    public Page<Project> getPage() {
        return page;
    }
}
```

```html
<!-- Good: preserve filters when moving between pages -->
<sly data-sly-use.model="com.example.core.models.ProjectListModel" />
<div class="pagination" data-sly-test="${model.page.hasPrevious}">
  <a href="?page=1&amp;title=${request.requestParameterMap.title[0].string}&amp;country=${request.requestParameterMap.country[0].string}">
    « First
  </a>
  <a href="?page=${model.page.previousPageNumber}&amp;title=${request.requestParameterMap.title[0].string}&amp;country=${request.requestParameterMap.country[0].string}">
    Previous
  </a>
</div>
```

This works because the browser only receives and renders one slice of the list at a time, while the current search/sort context stays intact across navigation.

### Client-side slice for already-loaded data

If the full dataset is already in memory and cannot be paged from the server yet, slice the rendered items so only one page is mounted.

```javascript
// Good: render only the current page slice
const ITEMS_PER_PAGE = 50;
let page = 0;

function renderPage(items) {
  const start = page * ITEMS_PER_PAGE;
  const end = start + ITEMS_PER_PAGE;
  const pageItems = items.slice(start, end);

  tableBody.replaceChildren(
    ...pageItems.map((item) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${item.name}</td><td>${item.status}</td>`;
      return tr;
    })
  );
}
```

This reduces DOM size immediately, even before a backend pagination endpoint exists. It is especially useful when the row template is heavy and each item carries links, tooltips, or nested controls.

### Keep the page number in the URL

```html
<!-- Good: server-rendered page links can also encode the page -->
<a href="?page={{ page_obj.next_page_number }}&search={{ request.GET.search }}">Next</a>
```

Keeping the page in the URL makes the list shareable, reloadable, and consistent with back/forward navigation.

## Anti-patterns

### Rendering the full list and hiding it with CSS

```html
<!-- Bad -->
<ul class="project-list">
  <sly data-sly-list.project="${projects}">
    <li class="project-row">${project.name}</li>
  </sly>
</ul>

<style>
  .project-row:nth-child(n + 13) {
    display: none;
  }
</style>
```

**Why this is bad:** All rows still enter the DOM, so layout and paint cost remain high even though only a subset is visible.

### Slicing only the API response but still mounting everything

```javascript
// Bad
const visibleItems = items.filter((item, index) => index < 12);
tableBody.replaceChildren(
  ...items.map((item) => {
    const tr = document.createElement('tr');
    tr.textContent = item.name;
    return tr;
  })
);
```

**Why this is bad:** The code computes a slice but still renders the full collection, so the browser pays the same DOM cost.

### Dropping pagination state when changing pages

```html
<!-- Bad -->
<a href="?page=2">Next</a>
```

**Why this is bad:** Search and filter context is lost on navigation, so users see the wrong slice and may think results disappeared.

### Using an "all rows" option as the default path

```html
<!-- Bad -->
<select name="pageSize">
  <option value="12">12</option>
  <option value="-1" selected>All</option>
</select>
```

**Why this is bad:** A default "show all" mode recreates the large DOM that pagination is supposed to avoid.

## Flavor-specific notes

### CS

Use server-side pagination in the controller or resolver that feeds the listing page, and pass the page object to the template instead of the full collection. If the page also exposes JSON for client-side hydration, serialize only the current page slice, not the entire dataset.

### AMS

Prefer JSP or controller-level pagination before the view layer renders repeated rows. If the page is built from a model object, make sure the model exposes the current page and total count separately so the JSP can render links without iterating the full result set.

### Headless

Apply pagination in the API layer and return `items`, `total`, and page metadata together. The frontend should request one page at a time and render only that page, rather than fetching the full collection and slicing it in the browser.