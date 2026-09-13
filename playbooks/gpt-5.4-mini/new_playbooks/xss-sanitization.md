---
issue_type: xss-sanitization
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
required_validation:
- unsafe_html_rendering_confirmed
- sanitization_library_available
- server_side_sanitization_path_known
- iframe_sandbox_requirement_confirmed
forbidden_techniques:
- pattern: dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html\s*:\s*[^}]+\}\s*\}
  reason: Don't introduce raw HTML injection without sanitization — this reopens XSS
    risk and bypasses the security fix
- pattern: <iframe\b[^>]*sandbox\s*=\s*["'][^"']*allow-scripts[^"']*["']
  reason: Don't sandbox with allow-scripts unless explicitly required — it weakens
    the isolation boundary and can re-enable script execution
- pattern: \binnerHTML\s*=
  reason: Don't assign to innerHTML directly — use sanitized HTML or a safe renderer
    instead
- pattern: \bDOMParser\s*\(
  reason: Don't parse untrusted HTML with DOMParser and then inject it — parsing alone
    is not sanitization
source_prs:
- ant-design/x#1388
- ant-design/x#1257
- ant-design/x#1413
- ant-design/x#1457
- ColeMurray/background-agents#373
- hashintel/hash#350
- iterative/dvc.org#3365
- launchdarkly/launchpad-ui#678
- okp4/dataverse-portal#109
- calcom/cal.com#7696
- transmissions11/flux#57
- dailydotdev/apps#1847
- dfinity/internet-identity#2100
- humanmade/hm-gutenberg-tools#134
- the-commons-project/shc-web-reader#85
---
# XSS sanitization

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** INP

## What this addresses

This issue type covers rendering user- or CMS-authored HTML safely when the UI currently injects markup directly into the DOM. The security goal is XSS prevention, but the implementation can also change post-paint rendering behavior and add work on the main thread, so it can affect INP when the content is large or frequently updated.

## When to apply / when to skip
**Apply when:**
- The component renders untrusted or semi-trusted HTML from authors, APIs, or rich-text fields
- The current implementation uses raw HTML injection, HTML parsing, or unsafe string concatenation
- The fix replaces direct DOM injection with sanitized output, or isolates the content in a sandboxed frame

**Skip when:**
- The content is already plain text and never interpreted as HTML
- The HTML is fully trusted and static, with no user-controlled input path
- The change would require a broader content-model migration rather than a local rendering fix

## Recommended approaches

### Sanitize before rendering into the existing container

Prefer sanitizing on the server or in the data layer, then render the sanitized HTML in the component. Keep the rendering path simple so the browser does not have to do extra parsing work after paint.

```java
// Good: sanitize once, then expose safe HTML from the server-side model
@Model(adaptables = SlingHttpServletRequest.class)
public class DescriptionModel {
  @Inject
  private String description;

  public String getDescriptionAsSafeHTML() {
    return HtmlSanitizer.sanitize(description);
  }
}
```

```html
<!-- Good: HTL renders the already-sanitized HTML string -->
<div class="description" data-sly-use.model="com.example.DescriptionModel">
  <sly data-sly-test="${model.descriptionAsSafeHTML}">
    ${model.descriptionAsSafeHTML @ context='html'}
  </sly>
</div>
```

This works because the browser receives already-sanitized markup, avoiding ad hoc client-side parsing and reducing the chance of repeated expensive transformations during interaction.

### Isolate rich content in a sandboxed iframe

When the content is complex, highly variable, or needs stronger isolation, render it in a sandboxed iframe and write only sanitized HTML into that document.

```html
<!-- Good: isolate untrusted composition HTML in a sandboxed frame -->
<iframe title="Rich content" sandbox=""></iframe>
```

```javascript
// Good: write sanitized HTML into the iframe document
const frame = document.querySelector('iframe[title="Rich content"]');
if (frame && frame.contentDocument) {
  frame.contentDocument.open();
  frame.contentDocument.write(
    '<!doctype html><html><body>' + safeHtml + '</body></html>'
  );
  frame.contentDocument.close();
}
```

This reduces the blast radius of any markup mistakes and keeps the host page’s interaction path more predictable, which is useful when the content is heavy or frequently re-rendered.

### Keep sanitization at the boundary, not in the view

```java
// Good: sanitize in the data layer
public String markdownAndSanitize(String input) {
  if (input == null || input.isEmpty()) {
    return "";
  }
  return sanitizeMarkdownToHtml(input);
}
```

```html
<!-- Good: the view only consumes safe HTML -->
<div class="post-body" data-sly-test="${model.bodyAsSafeHTML}">
  ${model.bodyAsSafeHTML @ context='html'}
</div>
```

This keeps the component focused on rendering and avoids repeated sanitization logic in multiple UI paths.

## Anti-patterns

### Raw HTML injection from authored content

```html
<!-- Bad -->
<div class="article-description" data-sly-use.model="com.example.DescriptionModel">
  ${model.description @ context='html'}
</div>
```

**Why this is bad:** It renders untrusted HTML directly into the DOM, which is the classic XSS sink this playbook is meant to remove.

### Parsing HTML in the browser and then injecting it unsafely

```javascript
// Bad
const doc = new DOMParser().parseFromString(userHtml, 'text/html');
const container = document.querySelector('.content');
container.innerHTML = doc.body.innerHTML;
```

**Why this is bad:** Parsing does not sanitize; it just turns attacker-controlled markup into DOM nodes and can still preserve dangerous payloads.

### Using a permissive iframe sandbox

```html
<!-- Bad -->
<iframe sandbox="allow-scripts allow-same-origin" title="Rich content"></iframe>
```

**Why this is bad:** Those flags weaken the isolation boundary enough that the frame can execute script and interact too broadly with its origin, undermining the security goal.

### Re-sanitizing on every render with heavy client-side transforms

```javascript
// Bad
function renderComment(html) {
  const safe = DOMPurify.sanitize(html);
  const container = document.querySelector('.comment');
  container.textContent = '';
  container.insertAdjacentHTML('beforeend', safe);
}
```

**Why this is bad:** Doing expensive sanitization work in the render path can add avoidable main-thread cost and make interaction latency worse when the content updates often.

## Flavor-specific notes

### CS

Prefer sanitizing in Sling models, servlets, or model exporters before the HTL layer receives the HTML string. If the component already has a model backing it, add a safe field such as `descriptionAsSafeHTML` and keep HTL dumb.

```java
@Model(adaptables = SlingHttpServletRequest.class)
public class ArticleModel {
  @Inject private String description;

  public String getDescriptionAsSafeHTML() {
    return sanitize(description);
  }
}
```

```html
<!-- Good -->
<div class="article-description" data-sly-test="${model.descriptionAsSafeHTML}">
  ${model.descriptionAsSafeHTML @ context='html'}
</div>
```

If the content is too dynamic or third-party generated, consider an iframe-based renderer only after confirming the sandbox requirements and the interaction cost.

### AMS

Use the same boundary-first approach, but verify the JSP/HTL output path carefully because legacy include chains can hide where the HTML is actually emitted. If the page already uses a server-side sanitizer utility, reuse it rather than adding a second client-side parser.

```jsp
<%-- Good: sanitize before writing markup --%>
<div class="bio">
  <%= HtmlSanitizer.sanitize(bioHtml) %>
</div>
```

Avoid adding browser-side parsing libraries just to “clean up” HTML after it reaches the page; that shifts work into the interaction path and can make INP worse.

### Headless

Prefer sanitizing in the API layer or content pipeline, then expose a safe HTML field to the client. If the frontend must render rich content from a CMS, keep the renderer deterministic and avoid per-interaction re-sanitization.

```ts
// Good: API returns safeHtml, UI renders it directly
type RichTextResponse = {
  safeHtml: string;
};

function RichText({ safeHtml }: RichTextResponse) {
  return <div dangerouslySetInnerHTML={{ __html: safeHtml }} />;
}
```

If the product requires untrusted embedded widgets or highly variable author HTML, use a sandboxed iframe and keep the host page’s event handling separate from the content frame.