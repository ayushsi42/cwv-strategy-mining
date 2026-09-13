---
issue_type: icon-font-bump
applicable_flavors:
- cs
- ams
- headless
risk_tier: low
forbidden_techniques: []
required_validation: []
source_prs:
- martincostello/costellobot#483
- martincostello/dependabot-helper#524
- martincostello/costellobot#968
- martincostello/dependabot-helper#985
- martincostello/costellobot#1542
- martincostello/dependabot-helper#1494
- martincostello/costellobot#1898
- martincostello/dependabot-helper#1815
- martincostello/costellobot#2557
- martincostello/dependabot-helper#2295
---
# Icon font bump

> **Risk tier:** low · **Applies to:** CS, AMS, Headless · **CWV metric:** LCP, FCP

## What this addresses

Updating an icon font package such as Font Awesome changes the CSS and font files that are requested before paint. That can affect render timing, especially when the icon stylesheet is in the shared shell and icons appear in the initial viewport.

This playbook is for safe, direct version bumps of the icon font CDN reference in shared HTML shells, where the fix is limited to swapping the stylesheet URL and its integrity hash.

## When to apply / when to skip
**Apply when:**
- The diff only updates the Font Awesome CDN stylesheet or equivalent icon-font CSS in a shared shell
- The icon set is used in initial markup, not injected later by JS
- The change is a version bump with the same delivery pattern, not a redesign of icon usage

**Skip when:**
- The icons are not in the initial render path
- The change requires replacing icon fonts with SVG sprites or inline SVGs
- The icon stylesheet is loaded conditionally per route and the issue is actually template scoping, not the font bump itself
- The site is EDS, where this playbook does not apply

## Recommended approaches

### Keep the icon stylesheet in the shared shell and update the version atomically

```html
<!-- Good: shared shell references the new Font Awesome release -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html">
  <sly data-sly-call="${clientlib.css @ categories='site.shared'}" />
</sly>
```

Keep the stylesheet reference and integrity hash aligned to the same release so the browser can fetch and apply the icon font deterministically before first paint.

### Preserve existing icon markup

```html
<!-- Good: existing icon usage remains stable -->
<button type="button" class="btn btn-secondary">
  <span class="fa fa-refresh" aria-hidden="true"></span>
  Refresh
</button>
```

A version bump should not require changing the icon usage pattern if the same icon names remain available. That keeps the change low risk and avoids introducing unrelated layout or accessibility regressions.

## Anti-patterns

### Mixing a version bump with an unrelated icon strategy change

```html
<!-- Bad: changing the delivery model at the same time as the version bump -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html">
  <sly data-sly-call="${clientlib.css @ categories='site.shared'}" />
</sly>

<!-- later -->
<svg class="icon icon-refresh" aria-hidden="true">
  <use href="/assets/icons.svg#refresh"></use>
</svg>
```

**Why this is bad:** Combining a font upgrade with an icon-system migration makes the performance effect harder to attribute and increases the chance of breaking initial paint or icon rendering.

### Loading the icon stylesheet after first paint

```html
<!-- Bad -->
<script>
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css';
  document.head.appendChild(link);
</script>
```

**Why this is bad:** Deferring the stylesheet with JS delays icon font discovery and can shift the first paint of icon-bearing UI.

### Leaving the integrity hash stale after the version bump

```html
<!-- Bad -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html">
  <sly data-sly-call="${clientlib.css @ categories='site.shared'}" />
</sly>
```

**Why this is bad:** A mismatched integrity hash can cause the browser to reject the stylesheet, which can remove icons entirely and create a visible render regression.

### Moving the icon stylesheet out of the shared shell without scoping it

```html
<!-- Bad -->
<!-- removed from the shared layout -->
<!-- added ad hoc in one page only -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html">
  <sly data-sly-call="${clientlib.css @ categories='site.page'}" />
</sly>
```

**Why this is bad:** Icon fonts used in shared chrome should stay in the shared shell; scattering the reference across pages makes pre-paint behavior inconsistent and easy to miss.