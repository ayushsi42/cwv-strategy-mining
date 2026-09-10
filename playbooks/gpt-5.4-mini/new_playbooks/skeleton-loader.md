---
issue_type: skeleton-loader
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
required_validation:
- server_rendered_placeholder_exists
- removal_trigger_is_data_or_font_ready
- placeholder_dimensions_match_final_content
- no_existing_page_level_skeleton
- no_accessibility_critical_content_hidden
forbidden_techniques: []
source_prs:
- vtex-sites/base.store#317
- x7ddf74479jn5/food-blog#51
- smartprocure/futil-js#368
- calcom/cal.com#4484
- safe-global/web-core#1577
- hlxsites/choice#21
- pln-planning-tools/Starmap#309
- danskernesdigitalebibliotek/dpl-design-system#192
- okp4/dataverse-portal#167
- adobe-experience-league/exlm#287
- Budibase/budibase#12898
- dailydotdev/apps#2825
- opencrvs/opencrvs-core#6894
---
# Skeleton loader

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** LCP, CLS

## What this addresses

A skeleton loader gives users an immediate, structured preview while real content is still loading. When the placeholder reserves the right space and is removed only after the real content is ready, it can reduce perceived loading delay and help prevent layout shifts during initial render.

## When to apply / when to skip

**Apply when:**
- The page has a meaningful server-rendered shell, but the real content arrives later from data fetches or client boot
- The loading state is visible long enough that a blank screen feels broken or unstable
- The placeholder can be rendered in the initial HTML and removed deterministically after data or font readiness

**Skip when:**
- The content is already fully available at first paint
- The loading state is extremely brief and a skeleton would flash
- The placeholder would hide essential content for too long or create accessibility issues
- The page is EDS and the skeleton would require a per-page server-side insertion path that does not exist in the fixed head/body structure

## Recommended approaches

### Server-rendered skeleton with stable dimensions

Render the skeleton in the server output, matching the final layout as closely as possible. Keep the placeholder in the DOM until the real content is ready, then remove or replace it.

```html
<!-- Good: server renders a stable placeholder -->
<div id="app-shell">
  <div id="clientAppSkeletonLoader" class="skeleton" aria-hidden="true">
    <div class="skeleton__header"></div>
    <div class="skeleton__card"></div>
    <div class="skeleton__line"></div>
    <div class="skeleton__line skeleton__line--short"></div>
  </div>

  <main id="app-content" hidden>
    <h1>Product title</h1>
    <p>Loaded content goes here.</p>
  </main>
</div>
```

```css
/* Good: reserve the same space the real content will occupy */
#clientAppSkeletonLoader {
  min-height: 480px;
}

.skeleton__card {
  height: 240px;
  border-radius: 16px;
  background: linear-gradient(90deg, #eee 25%, #f5f5f5 37%, #eee 63%);
}
```

This works because the browser can paint a meaningful structure immediately, and the reserved space reduces CLS when the real content replaces it.

### Remove the skeleton only after data and font readiness

If text metrics depend on web fonts, wait for both data and fonts before removing the placeholder.

```js
// Good: remove only when the real UI can render without shifting
let dataLoaded = false;
let fontsLoaded = false;

document.fonts.ready.then(() => {
  fontsLoaded = true;
  maybeRevealContent();
});

async function loadData() {
  await fetch('/api/page-data');
  dataLoaded = true;
  maybeRevealContent();
}

function maybeRevealContent() {
  if (dataLoaded && fontsLoaded) {
    document.getElementById('clientAppSkeletonLoader')?.remove();
    document.getElementById('app-content')?.removeAttribute('hidden');
  }
}
```

This avoids a common CLS pattern where content appears, then reflows again once fonts settle.

### Use component-scoped skeletons for repeated regions

For lists, cards, or post previews, skeletons should mirror the final component structure rather than using a generic full-page block.

```html
<!-- Good: list skeleton mirrors the card grid -->
<ul class="product-grid" aria-hidden="true">
  <li class="product-card-skeleton"></li>
  <li class="product-card-skeleton"></li>
  <li class="product-card-skeleton"></li>
  <li class="product-card-skeleton"></li>
</ul>
```

This keeps the loading state visually aligned with the eventual content and makes it easier to preserve spacing across breakpoints.

## Anti-patterns

### Blank screen until the app finishes booting

```html
<!-- Bad: nothing is shown until JS/data are ready -->
<div id="app"></div>
<script>
  hydrateApp();
</script>
```

**Why this is bad:** A blank viewport increases perceived load time and gives the browser no stable geometry to paint, which can worsen user experience and layout stability.

### Skeleton inserted only after client boot

```js
// Bad: the skeleton appears too late to help the initial load
window.addEventListener('load', () => {
  const skeleton = document.createElement('div');
  skeleton.id = 'clientAppSkeletonLoader';
  document.body.prepend(skeleton);
});
```

**Why this is bad:** If the placeholder is added after the page has already started rendering, it can cause an extra shift instead of preventing one.

### Removing the skeleton before the real content is ready

```js
// Bad: content may still be measuring or fetching
document.getElementById('clientAppSkeletonLoader')?.remove();
renderApp();
```

**Why this is bad:** Removing the placeholder too early exposes an unstable layout and can create a second shift when data, images, or fonts finish loading.

### Skeleton with mismatched height

```html
<!-- Bad: placeholder is much shorter than the final content -->
<div class="post-skeleton" style="height: 120px"></div>
<article class="post" style="height: 420px"></article>
```

**Why this is bad:** If the skeleton does not reserve the same space as the final content, the page will jump when the real UI replaces it, defeating the CLS benefit.

## Flavor-specific notes

### CS

Prefer server-rendered HTL placeholders or component markup that is emitted before client-side hydration. If the page uses Sling Models, expose a loading state from the model only when the component can render a stable skeleton without hiding critical content.

A typical pattern is to render the skeleton in HTL and swap it once the component data is available:

```html
<!-- Good: HTL skeleton wrapper -->
<sly data-sly-use.model="com.example.components.ProductListModel" />
<div class="product-list" data-loading="${!model.ready}">
  <div class="product-list__skeleton" data-sly-test="${!model.ready}" aria-hidden="true"></div>
  <ul data-sly-test="${model.ready}">
    <!-- real items -->
  </ul>
</div>
```

### AMS

Use JSP/HTL output to emit the placeholder directly from the server, and keep the skeleton CSS in a clientlib that is loaded with the component or template that needs it. Validate the rendered markup path, especially when the component is included through nested includes or legacy foundation components.

A common AMS pattern is to scope the skeleton to the component clientlib:

```xml
<!-- Good: component-scoped clientlib -->
<jcr:root
  jcr:primaryType="cq:ClientLibraryFolder"
  categories="[site.productlist]"
  dependencies="[site.base]" />
```

```jsp
<!-- Good: server-rendered placeholder -->
<div class="product-list">
  <c:if test="${empty products}">
    <div class="product-list__skeleton" aria-hidden="true"></div>
  </c:if>
  <c:if test="${not empty products}">
    <!-- real markup -->
  </c:if>
</div>
```

### Headless

Use the skeleton in the server-rendered shell or SSR layer that wraps the client app, and remove it only after both the data payload and font readiness are satisfied. Keep the placeholder accessible by marking it decorative when it is only a loading affordance.

```html
<!-- Good: SSR shell for a headless app -->
<div id="shell">
  <div id="clientAppSkeletonLoader" aria-hidden="true"></div>
  <div id="app-root"></div>
</div>
```

If the app is fully client-rendered with no SSR shell, this playbook is usually a recommendation rather than an auto-fix candidate.