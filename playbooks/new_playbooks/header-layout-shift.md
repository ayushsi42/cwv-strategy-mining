---
issue_type: header-layout-shift
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- header_element_identified
- initial_header_height_measured
- no_js_inserted_header_before_paint
- nav_toggle_state_traced
- sticky_or_fixed_offsets_reviewed
forbidden_techniques: []
source_prs:
- adobe-experience-league/exlm#55
- servicenow-martech/aemeds#8
- adobecom/milo#3434
- moCOMOco-main4/frontend#22
---
# Header layout shift

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** CLS

## What this addresses

A header refactor can change the size, position, or DOM order of the initial navigation before first paint. When the header grows, collapses, becomes sticky, or is inserted after load, the page content below it can move and CLS can increase.

This playbook covers header changes where the goal is to stabilize navigation layout without introducing new shifts during initial render or on menu open/close.

## When to apply / when to skip

**Apply when:**
- The header or nav is being redesigned, restyled, or restructured
- A promo bar, breadcrumb row, search row, or utility row is added above the main nav
- JS now inserts, removes, or reorders header children during decoration
- The header switches between fixed, sticky, or static positioning
- Lighthouse or field data shows CLS tied to the header area

**Skip when:**
- The issue is purely image sizing inside the header; use [`image-sizing.md`](./image-sizing.md)
- The shift is caused by fonts, not header structure; use [`font-display.md`](./font-display.md)
- The header is already stable and the CLS source is elsewhere
- The change only affects a non-initial interaction after user input and does not move unexpected content

## Recommended approaches

### Reserve the final header space in the initial HTML/CSS

```html
<!-- Good: header space is reserved before JS runs -->
<header class="site-header has-promo">
  <div class="site-header__promo"></div>
  <div class="site-header__nav">
    <a class="site-header__brand" href="/">Brand</a>
    <nav class="site-header__menu" aria-label="Main">
      <button class="site-header__toggle" aria-expanded="false">Menu</button>
    </nav>
  </div>
</header>
```

```css
.site-header {
  min-height: 128px;
}

.site-header__promo {
  height: 32px;
}

.site-header__nav {
  height: 96px;
}
```

Reserving the final footprint can help prevent the browser from reflowing the page when the header finishes decorating. If a promo or secondary row may appear, allocate that space up front even when the content is empty.

### Keep header decoration in-place instead of inserting above content later

```javascript
// Good: decorate existing header nodes, don't create a new wrapper above the page after paint
export default function decorate(block) {
  const header = block.querySelector('.site-header');
  const promo = header.querySelector('.site-header__promo');
  const nav = header.querySelector('.site-header__nav');

  if (promo) promo.hidden = false;
  if (nav) nav.classList.add('site-header__nav--ready');
}
```

Mutating existing header nodes is safer than inserting a new element before the header or before the first content block after the page has already painted.

### Use sticky/fixed offsets that match the reserved header height

```css
.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
}

.page-content {
  padding-top: 128px;
}
```

If the header is sticky or fixed, the content below it must already account for the occupied space. Matching the offset to the reserved height can avoid the “jump down” effect when the header becomes pinned.

## Anti-patterns

### Inserting a new header wrapper after decoration

```javascript
// Bad
export default function decorate(block) {
  const wrapper = document.createElement('div');
  wrapper.className = 'promo-wrapper';
  block.before(wrapper);
  wrapper.append(block.querySelector('.promo'));
}
```

**Why this is bad:** inserting a wrapper above the header after initial render can push the rest of the page down and create CLS.

### Changing header height only after JS loads

```css
/* Bad */
.site-header {
  min-height: 64px;
}

.site-header.has-promo {
  min-height: 128px;
}
```

```javascript
// Bad
if (hasPromo) {
  document.querySelector('.site-header').classList.add('has-promo');
}
```

**Why this is bad:** the page first paints at one height and then expands later, which can visibly shift the content below the header.

### Toggling layout-affecting classes without reserving space

```javascript
// Bad
const header = document.querySelector('header');
header.classList.add('has-search', 'has-breadcrumbs', 'has-promo');
```

```css
/* Bad */
header.has-promo .promo {
  display: block;
}
```

**Why this is bad:** if the added class changes the header’s intrinsic height or flow, the browser may need to recalculate layout and move content after paint.

### Replacing the header DOM instead of updating it

```javascript
// Bad
const header = document.querySelector('header');
header.outerHTML = `
  <header class="site-header">
    <div class="site-header__nav">...</div>
  </header>
`;
```

**Why this is bad:** replacing the header node discards the original layout and can cause a visible reflow when the new markup is inserted.

## Flavor-specific notes

### EDS

Prefer block decoration that keeps the header structure stable from the first paint. If a header promo or nav variant is needed, render the placeholder in the block markup and fill it in-place rather than prepending new DOM above the page content.

### CS

When the header is assembled from HTL and clientlibs, keep the header container height stable in the template and avoid clientlib-driven DOM insertion that changes the flow after the page has painted. If a new row is introduced, update the template markup and CSS together so the reserved height matches the final rendered header.

### AMS

Be careful with JSP or component includes that emit different header markup depending on authoring state, locale, or personalization. If the header can vary, reserve the maximum expected height in the base template and keep any conditional rows inside that footprint.

### Headless

Even in headless delivery, the same CLS rule applies to the client-rendered shell. Ensure the app shell reserves the header height before hydration or async navigation data arrives, and avoid mounting a taller header after the first paint.