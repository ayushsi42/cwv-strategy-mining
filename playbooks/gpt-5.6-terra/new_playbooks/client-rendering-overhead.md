---
issue_type: client-rendering-overhead
applicable_flavors:
- cs
- ams
risk_tier: high
required_validation: []
forbidden_techniques: []
source_prs:
- ghostty-org/website#425
- victory-sokolov/viktorsokolov#7
- etalab/annuaire-entreprises-site#896
- takeshape/penny#204
---
# Client rendering overhead

## What this addresses

The evidence PR migrated static pages, pages with Markdown parsing, and several client components to server components. It does not report measured LCP or INP results.

This is an architectural rendering-model migration, not a safe local optimization. The evidence supports evaluating whether static or content-driven output can be rendered on the server rather than by client components.

## When to apply / when to skip
**Apply when:**
- The affected page or component is static or content-driven.
- Content parsing or rendering can occur on the server.
- The component does not require client-side rendering for its primary content.

**Do not apply when:**
- The component must remain a client component for its required behavior.
- The proposed change has not accounted for styling and interaction regressions.

## Recommended approaches

### Move static and content-driven pages to server rendering

The evidence PR migrated static pages and pages with Markdown parsing to server components. For content that does not need client-side rendering, render the primary page output on the server.

### Keep client components only where needed

The evidence PR migrated remaining client components to the server while leaving a tooltip as a client component and making it accessible. Retain client-side rendering only for behavior that requires it.

### Verify styling and interaction behavior during migration

The PR review noted that moving pages could break `/departements` styles. Check component styling, client-side interactions, and page behavior when changing the rendering model.

## Anti-patterns

### Showing a copy indicator in normal document flow for large content

The PR review reported that, for large children, the appearance of a copy tag caused a large CLS. The reviewer noted that this was why an absolutely positioned element had previously been used.

```html
<!-- Bad: a copy indicator can change layout when it appears -->
<div class="copyable-content">
  <button>Copy</button>
  <span class="copy-status">Copied</span>
</div>
```

**Why this is bad:** for large content, making the copy tag appear can cause a large layout shift.

### Leaving copy feedback visible after focus is lost

The PR review reported that the “copié” feedback remained visible after blur.

```javascript
// Bad: copy feedback is shown but never cleared on blur
button.addEventListener('click', () => {
  status.textContent = 'Copied';
});
```

**Why this is bad:** the feedback can remain visible after the user has moved focus away.

## Flavor-specific notes

No CS- or AMS-specific implementation guidance is supported by the evidence PR.