---
issue_type: footer-render-blocking
applicable_flavors:
- cs
- ams
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- RetroAchievements/RAWeb#674
- blackberggroup/va-website-template#3
- aemsites/momentive#31
- EuroPython/website#1111
---
# Footer render blocking

> **Risk tier:** medium · **Applies to:** CS, AMS · **CWV metric:** CLS

## What this addresses

This issue covers footers that are hidden, unstyled, or only made visible after JavaScript runs. When the footer appears late or changes height after first paint, it can push content and create layout shifts that hurt CLS.

The safe fix is to render the footer in its final layout from the server/template, and if interactivity is needed, toggle only non-layout-affecting states after the space is already reserved.

## When to apply / when to skip
**Apply when:**
- The footer is present in the initial HTML but hidden until JS executes
- Footer styling depends on a script adding classes after load
- The footer’s reveal changes document flow height or pushes content downward
- Lighthouse or field data shows CLS tied to footer appearance or footer-related late style changes

**Skip when:**
- The footer is already visible and stable in the initial render
- The change is purely cosmetic and does not affect layout geometry
- The footer is client-rendered in a way that is outside the server/template path
- The issue is actually a different CLS source, such as images without dimensions or late-loading banners

## Recommended approaches

### Render the footer visible in the initial HTML

```html
<!-- Good: footer is part of the initial document flow -->
<footer class="site-footer">
  <div class="site-footer__inner">
    <nav aria-label="Footer">
      <ul class="site-footer__links">
        <li><a href="/about">About</a></li>
        <li><a href="/contact">Contact</a></li>
      </ul>
    </nav>
  </div>
</footer>
```

```css
.site-footer {
  display: block;
  padding: 2rem 1rem;
}
```

This keeps the footer in the layout from the start, so the browser can reserve space and paint it without a late reflow.

### Reserve space in CSS before any enhancement script runs

```html
<!-- Good: the footer has stable dimensions before JS enhancement -->
<footer class="site-footer site-footer--enhanced">
  <div class="site-footer__inner">
    <div class="site-footer__columns">
      <section>...</section>
      <section>...</section>
    </div>
  </div>
</footer>
```

```css
.site-footer {
  min-height: 18rem;
}

.site-footer--enhanced .site-footer__columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.5rem;
}
```

If JS later enhances the footer, the reserved space prevents the enhancement from pushing content around.

### Use JS only for non-layout behavior

```javascript
// Good: behavior only, no visibility or geometry changes
const footer = document.querySelector('.site-footer');
footer?.addEventListener('click', (event) => {
  const button = event.target.closest('[data-footer-toggle]');
  if (!button) return;

  const panel = footer.querySelector(button.getAttribute('aria-controls'));
  const expanded = button.getAttribute('aria-expanded') === 'true';
  button.setAttribute('aria-expanded', String(!expanded));
  panel?.toggleAttribute('hidden');
});
```

This is safe because the footer is already rendered and sized; the script only changes interaction state.

## Anti-patterns

### Hiding the footer until JS adds a class

```html
<!-- Bad -->
<footer class="site-footer is-hidden">
  ...
</footer>
```

```css
.is-hidden {
  display: none;
}
```

```javascript
window.addEventListener('load', () => {
  document.querySelector('.site-footer')?.classList.remove('is-hidden');
});
```

**Why this is bad:** The footer enters the layout late, so the page height changes after first paint and content below or above it can shift.

### Revealing the footer by mutating inline styles

```javascript
// Bad
const footer = document.querySelector('footer');
footer.style.display = 'block';
footer.style.opacity = '1';
```

**Why this is bad:** Inline style changes after load can trigger a late reflow and repaint, which can contribute to layout instability and CLS.

### Building footer structure only after script execution

```javascript
// Bad
const footer = document.querySelector('footer');
footer.innerHTML = `
  <div class="footer-columns">
    <section>...</section>
    <section>...</section>
  </div>
`;
```

**Why this is bad:** Replacing or injecting the footer markup after first paint changes the document flow and can move visible content.

### Collapsing footer sections with no reserved height

```css
/* Bad */
.site-footer__panel {
  height: 0;
  overflow: hidden;
}
```

```javascript
// Bad
document.querySelector('.site-footer__panel')?.classList.add('open');
```

**Why this is bad:** Expanding collapsed footer content after load changes the footer’s height and can shift the page.

## Flavor-specific notes

### CS

Prefer server-side template output for the footer and keep the footer markup stable across page templates. If the footer is assembled from a component or template include, make sure the include renders the final structure directly rather than waiting for a client-side enhancement step.

If a footer sub-navigation or accordion is needed, render the full footer container in HTML and use JS only to toggle `hidden`, `aria-expanded`, or other non-layout states on already-reserved panels.

### AMS

Verify the JSP or HTL output path that produces the footer before changing the visible state logic. In AMS, footer markup may come through includes or component scripts, so the fix should be applied where the server-rendered footer is emitted, not in a late DOM rewrite.

If the footer is currently hidden by default and shown by a script, move the default visibility into the template/CSS so the footer occupies its final space on first paint.