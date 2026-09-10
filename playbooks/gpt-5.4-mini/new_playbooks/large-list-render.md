---
issue_type: large-list-render
applicable_flavors:
- cs
- ams
- headless
risk_tier: low
required_validation:
- list_source_identified
- server_side_pagination_supported
- page_param_contract_known
- empty_state_behavior_defined
forbidden_techniques:
- pattern: <ul[^>]*>\s*(?:<li[^>]*>\s*.*?\s*</li>\s*){51,}</ul>
  reason: Don't keep rendering the full list in one DOM block — paginate or virtualize
    it so pre-paint work stays bounded
- pattern: JSON\.stringify\s*\(\s*[^)]*(?:items|users|projects|results)[^)]*\)
  reason: Don't serialize the full collection into the page payload — return only
    the current page of results
- pattern: pageSize\s*[:=]\s*(?:100|200|500|1000)
  reason: Don't 'fix' the problem by inflating the page size — that preserves the
    large render and payload cost
source_prs:
- ISPP-12/SarandONGa#617
- torchbox/torchbox.com#185
- CDCgov/prime-simplereport#8371
- awesome-academy/dn_oe61_nodejs-tran-van-duyet#3
---
# Large list render

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** LCP, INP

## What this addresses

Rendering and serializing a long list at once can increase HTML/JSON payload size, DOM work, and client-side diffing or layout cost. Paginating the list reduces pre-paint work and interaction cost, which can improve LCP and INP on list-heavy pages such as projects, users, or team listings.

## When to apply / when to skip
**Apply when:**
- The page renders a long collection in one pass and the list is visibly large or unbounded
- The server or resolver already owns the list data and can return a page slice
- The UI can preserve the current filter/search/sort state across page changes

**Skip when:**
- The list is already small and bounded by design
- The page is a true infinite feed where virtualization is the intended pattern and already implemented
- The collection is only used for a non-visual export or background task
- The page is EDS-delivered; this playbook does not apply there

## Recommended approaches

### Server-side pagination with a stable page parameter

Return only the current page of items from the server, and keep the page number in the URL so the state is shareable and crawlable.

```java
// Good: resolver returns one page, not the full collection
@Controller
public class ProjectResolver {

  public ProjectPage projects(
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(defaultValue = "20") int pageSize,
      @RequestParam(required = false) String search) {

    if (search == null) {
      search = "";
    }

    return projectService.getPagedProjects(page, pageSize, search);
  }
}
```

```html
<!-- Good: template renders only the current page -->
<ul class="project-list">
  <li data-sly-list.project="${model.projects.items}">
    <a href="${project.url}">${project.title}</a>
  </li>
</ul>

<nav aria-label="Pagination">
  <a href="${model.prevPageUrl}">Previous</a>
  <span>Page ${model.pageNumber} of ${model.totalPages}</span>
  <a href="${model.nextPageUrl}">Next</a>
</nav>
```

This keeps the DOM smaller, reduces serialization cost, and avoids forcing the browser to parse and lay out items the user cannot see yet.

### Preserve filters while paging

When the list is searchable or filterable, carry the active filter state into the page links so pagination does not reset the user’s context.

```html
<!-- Good -->
<a href="/projects?page=2&search=${searchTerm}">2</a>
<a href="/projects?page=3&search=${searchTerm}">3</a>
```

This avoids extra back-and-forth interactions and keeps INP lower by reducing repeated full-list re-renders.

### Headless: page the API response, not the client array

```json
{
  "items": [
    { "id": "p1", "title": "Project Alpha" },
    { "id": "p2", "title": "Project Beta" }
  ],
  "page": 1,
  "pageSize": 20,
  "totalItems": 184,
  "totalPages": 10
}
```

```js
// Good: request only the current page
const res = await fetch(`/api/projects?page=${page}&pageSize=20&search=${encodeURIComponent(search)}`);
const data = await res.json();
renderProjects(data.items);
renderPagination(data.page, data.totalPages);
```

This keeps the payload bounded and prevents the client from paying the cost of rendering a huge array all at once.

## Anti-patterns

### Rendering the full collection in one DOM block

```html
<!-- Bad -->
<ul class="project-list">
  <li data-sly-list.project="${model.allProjects}">
    <a href="${project.url}">${project.title}</a>
  </li>
</ul>
```

**Why this is bad:** A long unpaginated list can increase HTML size, DOM construction, and layout work before the page becomes usable.

### Serializing the entire list into the page

```java
// Bad
model.put("projectsJson", new ObjectMapper().writeValueAsString(projectService.findAllProjects()));
```

```html
<script>
  window.__PROJECTS__ = ${projectsJson @ context='unsafe'};
</script>
```

**Why this is bad:** Shipping the full collection to the browser can inflate the response and make the client parse and render far more data than the user can see.

### Hiding the problem with a huge page size

```java
// Bad
return projectService.getPagedProjects(page, 500, search);
```

**Why this is bad:** A very large page size keeps the same rendering and payload cost, so the CWV problem remains even though the UI now has page controls.

### Client-side slicing after fetching everything

```js
// Bad
const allProjects = await fetch('/api/projects').then(r => r.json());
const pageItems = allProjects.slice((page - 1) * 20, page * 20);
renderProjects(pageItems);
```

**Why this is bad:** The browser still downloads, parses, and holds the full dataset, so you only move the cost around instead of reducing it.

## Flavor-specific notes

### CS

Prefer server-side pagination in the Sling model or backing servlet, then expose only the current page to HTL. Keep the page number in the URL and preserve search/filter parameters in generated links.

```java
// Example shape for a Sling model-backed list
@Model(adaptables = SlingHttpServletRequest.class)
public class ProjectListModel {

  @Inject
  private ProjectService projectService;

  public Page<Project> getProjects() {
    return projectService.findPagedProjects(currentPage, pageSize, searchTerm);
  }
}
```

```html
<sly data-sly-use.model="com.example.core.models.ProjectListModel">
  <ul>
    <li data-sly-list.project="${model.projects.content}">
      <a href="${project.path}">${project.title}</a>
    </li>
  </ul>
</sly>
```

### AMS

Use the JSP or backing servlet to page the collection before it reaches the template. If the page already uses a request attribute or model object for the list, replace the full list with a paged wrapper and render pagination controls from that wrapper.

```jsp
<%-- Good: render only the current page --%>
<c:forEach var="project" items="${pagedProjects.items}">
  <li><a href="${project.url}">${project.title}</a></li>
</c:forEach>
```

Be careful to keep the query string state intact when generating page links, especially when the list is also filtered by search or category.

### Headless

Implement pagination in the API contract and keep the client rendering limited to the current page. If the frontend uses a framework, the fix still belongs in the data-fetching layer, not in a larger client-side array render.