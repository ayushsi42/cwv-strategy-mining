---
issue_type: content-loading-gaps
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: high
required_validation: []
forbidden_techniques: []
source_prs:
- Bilgisayar-Kavramlari-Toplulugu/project-learnops#269
- vtex-sites/base.store#317
- kedro-org/kedro-viz#1041
- danskernesdigitalebibliotek/dpl-design-system#192
- Budibase/budibase#12898
- SalesforceCommerceCloud/pwa-kit#2064
- SE-UUlm/snowballr-frontend#193
- woocommerce/woocommerce#58782
---
# Content loading gaps

> **Risk tier:** high · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** LCP, CLS

## What this addresses

Asynchronously loaded data or client-rendered regions can leave prominent page areas blank while requests, scripts, fonts, or hydration complete. The evidence includes skeletons used while lazy-loaded components or data are loading, including skeletons inserted into an initial server document and removed when the client is ready to render.

This is recommendation-only: a visually plausible placeholder can still be inappropriate if its dimensions, dismissal timing, or data lifecycle are wrong.

## When to apply / when to skip
**Apply when:**
- A loading gap leaves a visible, meaningful region blank while data or a deferred client module loads
- The region's final desktop and mobile dimensions are known from the rendered component, including image aspect ratios, typography, and repeated-item counts
- The loading lifecycle is traceable: initial load, successful data response, refetch, error, and cancellation states are all known
- The skeleton can be emitted with the initial document or existing component markup rather than requiring a new application architecture
- Existing content can remain visible during a background refetch when only a subsection is changing

**Skip when:**
- The async region is below the fold or is not visibly blank to users
- The final layout is data-dependent enough that a stable reservation cannot be defined
- The request normally completes quickly enough that users see a flash of placeholder content
- The fix would require changing a global rendering, hydration, or data-fetching architecture without page-specific review
- A full-region skeleton would be shown during a background refetch while already-rendered content can remain usable

## Recommended approaches

### Reserve the final component geometry in initial markup

Render a skeleton in the same component container and use responsive grid rules that follow the final content. Remove it after final content is ready to render.

```html
<!-- Good: initial markup emitted by the component/template -->
<section class="product-results" aria-busy="true" data-loading-region>
  <div class="product-results__grid product-results__grid--skeleton"
       aria-hidden="true"
       data-skeleton>
    <article class="product-card product-card--skeleton">
      <div class="product-card__media skeleton-block"></div>
      <div class="product-card__body">
        <span class="skeleton-line skeleton-line--title"></span>
        <span class="skeleton-line skeleton-line--price"></span>
      </div>
    </article>
    <article class="product-card product-card--skeleton">
      <div class="product-card__media skeleton-block"></div>
      <div class="product-card__body">
        <span class="skeleton-line skeleton-line--title"></span>
        <span class="skeleton-line skeleton-line--price"></span>
      </div>
    </article>
  </div>

  <div class="product-results__grid" data-content hidden></div>
</section>
```

```css
/* Good: reservation follows the final product-card geometry */
.product-results__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.product-card__media {
  aspect-ratio: 1 / 1;
}

.product-card__body {
  min-height: 76px;
  padding-top: 12px;
}

.skeleton-block,
.skeleton-line {
  display: block;
  background: #e7e7e7;
  border-radius: 4px;
}

.skeleton-line--title {
  width: 80%;
  height: 20px;
}

.skeleton-line--price {
  width: 45%;
  height: 16px;
  margin-top: 12px;
}

@media (min-width: 768px) {
  .product-results__grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
```

The evidence includes skeleton implementations with component-specific dimensions and separate desktop and mobile presentations.

### Keep rendered content during a background refresh

For a refetch, preserve stable content such as images, titles, and layout, and show a small skeleton only for the data that is changing.

```html
<!-- Good: existing product stays visible while only price/promotion refreshes -->
<article class="product-card" data-product-card>
  <img src="/content/dam/site/product.jpg"
       alt="Product name"
       width="480"
       height="480">

  <h2 class="product-card__title">Product name</h2>

  <div class="product-card__pricing" aria-live="polite" aria-busy="true">
    <span class="skeleton-line skeleton-line--price"
          aria-hidden="true"
          data-price-skeleton></span>
    <span class="visually-hidden">Updating price and promotion</span>
  </div>
</article>
```

```javascript
// Good: blocks/product-card/product-card.js
export default function decorate(block) {
  const productId = block.dataset.productId;
  const refreshButton = block.querySelector('[data-refresh-pricing]');

  async function refreshPricing() {
    const pricing = block.querySelector('.product-card__pricing');
    const placeholder = block.querySelector('[data-price-skeleton]');

    pricing.setAttribute('aria-busy', 'true');
    placeholder.hidden = false;

    try {
      const response = await fetch(
        `/api/products/${encodeURIComponent(productId)}/pricing`,
      );
      if (!response.ok) {
        throw new Error(`Pricing request failed: ${response.status}`);
      }

      const data = await response.json();
      pricing.innerHTML = `<span class="product-card__price">${data.formattedPrice}</span>`;
    } finally {
      pricing.setAttribute('aria-busy', 'false');
    }
  }

  refreshButton?.addEventListener('click', refreshPricing);
}
```

This follows the evidence that, during product refetching, pricing and promotion placeholders can be shown without replacing the entire product tile.

### EDS: decorate an existing reserved block and replace it atomically

Keep the skeleton in the authored block output, preserve its layout until data and the block module are ready, then replace only the loading region.

```javascript
// blocks/recommendations/recommendations.js
export default function decorate(block) {
  const load = async () => {
    const { renderRecommendations } = await import('./recommendations-content.js');
    const endpoint = block.dataset.endpoint;

    try {
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error(`Recommendations request failed: ${response.status}`);

      const items = await response.json();
      await renderRecommendations(block, items);

      block.querySelector('[data-skeleton]')?.remove();
      block.removeAttribute('aria-busy');
    } catch (error) {
      block.querySelector('[data-skeleton]')?.remove();
      block.insertAdjacentHTML(
        'beforeend',
        '<p class="recommendations__error">Recommendations are unavailable.</p>',
      );
      block.removeAttribute('aria-busy');
    }
  };

  load();
}
```

```html
<!-- Good: authored EDS block markup before decoration -->
<div class="recommendations" data-endpoint="/recommendations.json" aria-busy="true">
  <div class="recommendations__grid" data-skeleton aria-hidden="true">
    <div class="recommendations__card recommendations__card--skeleton"></div>
    <div class="recommendations__card recommendations__card--skeleton"></div>
    <div class="recommendations__card recommendations__card--skeleton"></div>
  </div>
</div>
```

The initial block markup keeps a loading representation in the region until the content renderer has inserted final markup.

### CS/AMS: emit a template-scoped reservation and transition through the existing clientlib

Scope the placeholder to the component and template where the asynchronous region occurs. Render the known component structure, then let the component clientlib replace its own loading state.

```java
// Good: core/src/main/java/com/example/site/core/models/ResultsModel.java
package com.example.site.core.models;

import org.apache.sling.api.SlingHttpServletRequest;
import com.adobe.cq.export.json.ComponentExporter;
import org.apache.sling.models.annotations.Model;
import org.apache.sling.models.annotations.DefaultInjectionStrategy;

@Model(
    adaptables = SlingHttpServletRequest.class,
    adapters = ComponentExporter.class,
    resourceType = "example/components/results",
    defaultInjectionStrategy = DefaultInjectionStrategy.OPTIONAL
)
public class ResultsModel implements ComponentExporter {
    public int getSkeletonItemCount() {
        return 4;
    }

    @Override
    public String getExportedType() {
        return "example/components/results";
    }
}
```

```html
<!-- Good: ui.apps/.../components/results/results.html -->
<sly data-sly-use.results="com.example.site.core.models.ResultsModel" />

<section class="results" data-results data-endpoint="${resource.path}.results.json" aria-busy="true">
  <div class="results__grid" data-skeleton aria-hidden="true">
    <article class="results__card results__card--skeleton"
             data-sly-repeat.item="${results.skeletonItemCount}">
      <div class="results__media"></div>
      <div class="results__line results__line--title"></div>
      <div class="results__line results__line--meta"></div>
    </article>
  </div>
  <div class="results__grid" data-results-content hidden></div>
</section>
```

```xml
<!-- Good: ui.apps/.../clientlibs/clientlib-results/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.results]"
          dependencies="[example.site.base]"/>
```

```text
# Good: ui.apps/.../clientlibs/clientlib-results/js.txt
#base=js
results.js
```

```javascript
// Good: ui.apps/.../clientlibs/clientlib-results/js/results.js
document.querySelectorAll('[data-results]').forEach(async (region) => {
  const content = region.querySelector('[data-results-content]');

  try {
    const response = await fetch(region.dataset.endpoint);
    if (!response.ok) {
      throw new Error(`Results request failed: ${response.status}`);
    }

    content.innerHTML = await response.text();
    content.hidden = false;
    region.querySelector('[data-skeleton]')?.remove();
  } catch (error) {
    region.querySelector('[data-skeleton]')?.remove();
    region.insertAdjacentHTML(
      'beforeend',
      '<p class="results__error">Results are unavailable.</p>',
    );
  } finally {
    region.setAttribute('aria-busy', 'false');
  }
});
```

This keeps the loading transition scoped to the component rather than using a site-wide loading overlay.

## Anti-patterns

### Replacing an entire populated region during a background refresh

```html
<!-- Bad: discard stable product cards whenever only pricing is refreshing -->
<ul class="product-grid" data-product-grid>
  <li class="product-card product-card--skeleton"></li>
  <li class="product-card product-card--skeleton"></li>
  <li class="product-card product-card--skeleton"></li>
  <li class="product-card product-card--skeleton"></li>
</ul>
```

```javascript
// Bad: blocks/product-grid/product-grid.js
export default function decorate(block) {
  if (block.dataset.refetching === 'true') {
    block.replaceChildren(...createFullProductGridSkeleton());
  }
}

function createFullProductGridSkeleton() {
  return Array.from({ length: 4 }, () => {
    const item = document.createElement('li');
    item.className = 'product-card product-card--skeleton';
    return item;
  });
}
```

**Why this is bad:** The evidence shows an alternative in which only pricing and promotions display a skeleton during product refetching, while the rest of the product tile remains rendered.

### Showing a skeleton for every request, including fast responses

```javascript
// Bad: blocks/dashboard/dashboard.js
export default async function decorate(block) {
  block.innerHTML = '<div class="dashboard__skeleton"></div>';

  const response = await fetch(block.dataset.endpoint);
  const data = await response.json();

  const dashboard = document.createElement('div');
  dashboard.className = 'dashboard';
  dashboard.textContent = data.title;
  block.replaceChildren(dashboard);
}
```

**Why this is bad:** Review feedback in the evidence notes that always showing a skeleton can produce a visible flash on fast connections.

### Removing the reservation before final content can occupy it

```html
<!-- Bad: removing the placeholder immediately leaves a blank collapsing region -->
<section class="search-results" data-results>
  <div class="search-results__skeleton" data-skeleton></div>
  <div data-results-content></div>
</section>
```

```javascript
// Bad: blocks/search-results/search-results.js
export default async function decorate(block) {
  block.querySelector('[data-skeleton]')?.remove();

  const response = await fetch(block.dataset.endpoint);
  block.querySelector('[data-results-content]').innerHTML = await response.text();
}
```

**Why this is bad:** This removes the loading representation before the asynchronous response has rendered content.

### Using arbitrary skeleton dimensions unrelated to the final component

```css
/* Bad: generic dimensions do not reserve the card's final image and text layout */
.results__card--skeleton {
  height: 40px;
  width: 100%;
}
```

```html
<!-- Bad -->
<article class="results__card results__card--skeleton"></article>
```

**Why this is bad:** The evidence uses component-specific skeleton structures and dimensions rather than a single generic placeholder shape.

## Flavor-specific notes

### EDS

Prefer skeleton markup in the block's initial authored HTML so it is visible before block JavaScript runs. Keep the skeleton scoped to the block and remove it after the content renderer has inserted final markup.

Do not make a generic site-wide `load` event remove all skeletons. Each block should own its request, success, and error lifecycle so a failed or deferred block can be handled by that block.

### CS

Identify the page template and component resource type before recommending a skeleton. A component reused across landing, product, and article templates may have different final geometry and loading relevance on each template.

Place component JavaScript in a template-scoped or component-scoped clientlib category. If server-side data is available through a Sling Model, consider rendering final content rather than adding a client-side skeleton.

### AMS

Verify the rendered JSP or HTL inclusion chain on publish before changing a placeholder. Legacy components can have nested `<cq:include>` paths and CSS inherited from template-level clientlibs, so the apparent component file may not control its output dimensions.

Avoid inserting a skeleton into a broadly shared foundation component without manual review.

### Headless

The consuming application should render the reservation in its initial shell for the route where the loading gap occurs; a content response alone does not create browser layout. Match the consumer's final responsive layout and keep existing content visible during data refetches.

Confirm whether the consumer server-renders the route, hydrates it, or renders entirely client-side before choosing a loading state. The evidence includes a skeleton inserted into the server-returned document and removed after the client app is ready to render.