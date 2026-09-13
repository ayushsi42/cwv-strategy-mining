---
issue_type: nav-structure-refactor
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
required_validation:
- nav_is_lcp_or_above_fold
- current_nav_markup_identified
- css_scope_change_traced
- no_fixed_height_or_width_assumptions_broken
forbidden_techniques:
- pattern: (?:^|\\n)\\s*nav\\s*\\{
  reason: Matches a known anti-pattern from the source evidence.
- pattern: display\\s*:\\s*none\\s*;
  reason: Matches a known anti-pattern from the source evidence.
- pattern: height\\s*:\\s*auto\\s*;
  reason: Matches a known anti-pattern from the source evidence.
source_prs:
- withstudiocms/studiocms#1112
- redpanda-data/console#1881
- elastic/kibana#132210
- mozilla/blurts-server#2825
- elastic/kibana#163102
---
# Nav structure refactor

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** LCP, CLS

## What this addresses

Reorganizing navigation markup and styling can change the pre-paint layout, especially for fixed sidebars, headers, and primary nav rails. That can shift the largest contentful paint candidate or introduce layout shifts if the new structure changes spacing, wrapping, or reserved space.

## When to apply / when to skip

**Apply when:**
- The PR changes navigation DOM structure, class names, or hierarchy
- The nav is visible above the fold or participates in the initial viewport layout
- The CSS change alters padding, display mode, positioning, or icon/text composition
- The sidebar or top nav is part of the LCP path or can push the main content down

**Skip when:**
- The change is purely semantic and does not affect rendered box geometry
- The nav is fully off-canvas until after user interaction
- The change is limited to non-layout text copy or ARIA labels
- The page uses a client-only shell where the nav is not part of the initial paint

## Recommended approaches

### Preserve the nav footprint while refactoring structure

Keep the outer container dimensions stable and move internal markup only when possible.

```html
<!-- Good: same outer nav footprint, internal structure refactored safely -->
<sly data-sly-use.navModel="com.example.core.models.NavigationModel" />
<nav class="site-nav" aria-label="${navModel.ariaLabel}">
  <div class="pages-nav">
    <a href="/user/breaches" class="nav-item current">Data breaches</a>
    <a href="/user/data-removal" class="nav-item">Data removal</a>
  </div>

  <div class="meta-nav">
    <a href="/user/settings" class="nav-item">Settings</a>
    <a href="/help" class="nav-item">Help and Support</a>
  </div>
</nav>
```

```css
/* Good: preserve fixed positioning and reserved space */
.site-nav {
  position: fixed;
  top: var(--header-h);
  left: 0;
  width: 18rem;
  height: calc(100vh - var(--header-h));
  box-sizing: border-box;
}
```

This works because the browser can keep the same layout reservation while the internal grouping changes. The nav can be modernized without forcing a new pre-paint geometry.

### Keep icon/text additions from changing line wrapping

If adding icons, reserve space explicitly so the label does not reflow.

```html
<!-- Good: icon has fixed box, label stays aligned -->
<a href="/user/breaches" class="nav-item current">
  <svg class="nav-icon" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"></svg>
  <span class="nav-label">Data breaches</span>
</a>
```

```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.nav-icon {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
}
```

This avoids text wrapping and keeps the nav row height stable, which reduces CLS risk during first paint.

### Update CSS in lockstep with markup changes

When the DOM structure changes, update selectors so the new structure does not inherit unintended defaults.

```css
/* Good: explicit selectors for the new structure */
.site-nav .pages-nav,
.site-nav .meta-nav {
  display: flex;
  flex-direction: column;
}

.site-nav .nav-item {
  padding: var(--padding-sm) var(--padding-lg);
  text-decoration: none;
}
```

This works because the browser applies predictable layout rules to the new hierarchy instead of falling back to generic selectors that may no longer match.

## Anti-patterns

### Changing nav structure without preserving dimensions

```html
<!-- Bad -->
<sly data-sly-use.navModel="com.example.core.models.NavigationModel" />
<nav class="site-nav" aria-label="${navModel.ariaLabel}">
  <div class="pages-nav">
    <a href="/user/breaches" class="nav-item">Data breaches</a>
    <a href="/user/data-removal" class="nav-item">Data removal</a>
  </div>
  <div class="meta-nav">
    <a href="/user/settings" class="nav-item">Settings</a>
  </div>
</nav>
```

```css
/* Bad: padding/width changed at the same time as structure */
.site-nav {
  padding: var(--padding-lg) var(--padding-lg) var(--footer-h);
  display: inline-flex;
  flex-flow: column nowrap;
}
```

**Why this is bad:** Structural and spacing changes together can alter the nav’s pre-paint footprint, which can shift surrounding content and create CLS.

### Adding icons or secondary links without reserving space

```html
<!-- Bad -->
<a href="/user/breaches" class="nav-item">
  <svg width="24" height="24" viewBox="0 0 24 24"></svg>
  Resolve Data Breaches
</a>
```

**Why this is bad:** New inline content can change line wrapping and row height, causing the sidebar to reflow after initial layout.

### Broad selector changes that affect all navs

```css
/* Bad */
.site-nav {
  padding: 2rem;
  display: flex;
}
```

**Why this is bad:** Global nav selectors can unintentionally restyle unrelated navigation components, expanding the blast radius and making layout shifts harder to predict.

### Toggling visibility with layout-affecting defaults

```js
// Bad
const nav = document.querySelector('.site-nav')
nav.style.display = 'block'
nav.style.height = 'auto'
```

**Why this is bad:** Forcing display and auto height in script can trigger a second layout pass and move content after first paint.

## Flavor-specific notes

### CS

For CS, navigation is often rendered through server-side templates plus client-side CSS/JS. Trace the template that emits the nav before changing selectors, and keep the server-rendered structure and CSS in sync.

If the nav is part of the initial page shell, validate that the refactor does not change the header/sidebar reservation used by the main content container.

### AMS

On AMS, nav markup may come from JSP, HTL, or included fragments. Verify the actual rendered output path before editing CSS, because include chains can produce a different DOM than the obvious source file suggests.

Be especially careful with fixed sidebars and legacy grid wrappers: a small padding or display change can cascade into a visible CLS issue.

### Headless

In headless shells, the nav is usually client-rendered. Apply this playbook only when the nav is present in the initial HTML shell or when the refactor changes the app frame that is visible before hydration.

If the nav is hydrated after first paint, prioritize preserving the server-rendered placeholder size so the client render does not shift the page.