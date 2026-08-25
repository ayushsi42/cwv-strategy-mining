---
issue_type: font-delivery--reduce-font-blocking-during-first-render
parent_strategy: font-delivery
risk_tier: low
cwv_metrics: [LCP, render-blocking resources]
source_prs: [woowacourse/perf-basecamp#177, axone-protocol/docs#730]
required_validation:
  - font_stylesheet_loaded_asynchronously
  - remote_font_origin_preconnected
  - fallback_font_stack_present
forbidden_techniques: []
---

# Reduce font blocking during first render

> **Risk tier:** low · **Parent strategy:** font-delivery · **CWV metrics:** LCP, render-blocking resources

## Purpose

This strategy reduces first-render delay caused by webfont delivery.

The evidence supports two mechanisms:

1. **Make the font request less blocking**
   - Preconnect to remote font origins before the stylesheet request.
   - Load the font stylesheet in a non-blocking shape so rendering can continue.

2. **Allow text to paint before the custom font is ready**
   - Keep a fallback font stack in base typography.
   - Use `font-display: swap` when you control the `@font-face` declaration.

## Apply / Skip

### Apply when
- The page uses remote webfonts in the initial render path.
- Lighthouse reports font-related render-blocking resources.
- The page can tolerate fallback text during the first paint.
- Readable text can remain visible while the custom font loads.

### Skip when
- The page uses only local or system fonts.
- The font is not part of the first-render path.
- Hiding text until the font is available is an intentional, validated design choice.
- You cannot confirm that the font stylesheet or `@font-face` declaration is actually involved in first render.

## Required validation

### `font_stylesheet_loaded_asynchronously`
**What this means:** the font stylesheet is not loaded as a plain blocking stylesheet during first render.

**Evidence that satisfies it:**
- A font stylesheet is preloaded and then promoted to stylesheet on load.
- A stylesheet is loaded with a non-blocking pattern such as `media="print"` plus `onload`.
- A `noscript` fallback exists when the non-blocking pattern depends on JavaScript.

**How to verify:**
- Inspect the document head and confirm the font CSS request is present.
- Confirm it is not left as a straightforward blocking stylesheet in the critical path.
- Confirm the page still renders readable fallback text while the font is pending.

### `remote_font_origin_preconnected`
**What this means:** the page includes preconnect hints for the remote font origins used by the stylesheet.

**Evidence that satisfies it:**
- `preconnect` to `https://fonts.googleapis.com`
- `preconnect` to `https://fonts.gstatic.com`

**How to verify:**
- Confirm the hints appear before the stylesheet request.
- Confirm the hints target the same remote hosts used by the font CSS.

### `fallback_font_stack_present`
**What this means:** the base typography includes a readable fallback stack.

**Evidence that satisfies it:**
- The body or base text rule includes the webfont plus system or generic fallbacks.
- The page can still paint text immediately if the custom font is unavailable.

**How to verify:**
- Inspect the computed font-family stack.
- Confirm the custom font is not the only font in the stack.
- Confirm text remains readable before the webfont finishes loading.

## Recommended approaches

### 1) Preconnect to remote font origins and load the stylesheet non-blockingly

The evidence shows `preconnect` hints for Google Fonts origins and a font stylesheet in the document head. It also shows a non-blocking stylesheet pattern using preload, stylesheet promotion on load, and a `noscript` fallback.

**Good**
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />

<link
  rel="preload"
  as="style"
  href="https://fonts.googleapis.com/css2?family=Josefin+Sans:ital,wght@0,400;0,700;1,400;1,700&display=swap&subset=latin"
/>
<link
  rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Josefin+Sans:ital,wght@0,400;0,700;1,400;1,700&display=swap&subset=latin"
  media="print"
  onload="this.media='all'"
/>
<noscript>
  <link
    rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Josefin+Sans:ital,wght@0,400;0,700;1,400;1,700&display=swap&subset=latin"
  />
</noscript>
```

**Why this is evidence-derived**
- It preserves the preconnect optimization.
- It avoids a plain blocking stylesheet path.
- It keeps a no-JS fallback.

### 2) Keep a readable fallback stack in base typography

The evidence shows the base font stack was expanded to include system fallbacks and `font-synthesis: none`.

**Good**
```css
body {
  font-family: 'Josefin Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-synthesis: none;
}
```

**Why this is evidence-derived**
- The custom font remains first in the stack.
- The browser can paint immediately with a fallback if the webfont is not ready.

### 3) Use `font-display: swap` when you control the font-face declaration

The child strategy summary identifies `font-display: swap` as the mechanism that lets the browser paint text immediately with a fallback font instead of hiding it until the custom font finishes downloading.

**Good**
```css
@font-face {
  font-family: "Example Sans";
  src: url("/fonts/example-sans.woff2") format("woff2");
  font-display: swap;
}
```

**Why this is evidence-derived**
- It directly matches the described mechanism.
- It avoids invisible text during font download.

## Evidence-derived examples

### Good
- `preconnect` hints are added for `fonts.googleapis.com` and `fonts.gstatic.com`.
- The font stylesheet is loaded with a non-blocking pattern rather than as a plain blocking stylesheet.
- The base font stack includes system fallbacks after the webfont.
- `font-display: swap` is the mechanism identified by the strategy summary.

### Bad
- A remote font stylesheet is left as a plain blocking stylesheet in the document head.
- The remote font origin is used without preconnect hints.
- The base typography uses only the custom font with no fallback stack.
- The font-face hides text until the font download completes instead of allowing fallback paint.

## Verification

Use the same measurement family referenced by the evidence:
- Lighthouse performance
- Lighthouse render-blocking resources
- Lighthouse font-display audit
- Lighthouse LCP

Verify before and after by checking:
- whether font-related render-blocking resources are reduced or removed from the critical path
- whether the font-display audit reflects the intended non-blocking behavior
- whether LCP improves or remains stable after the change

Do not assume a fixed improvement amount. The evidence supports directionality, not a universal delta.

## Evidence

### Observed facts
- One patch added `preconnect` hints for `fonts.googleapis.com` and `fonts.gstatic.com`, and loaded a Google Fonts stylesheet in the document head.
- One patch changed font loading to a non-blocking stylesheet pattern using `preload`, `media="print"`, `onload`, and a `noscript` fallback.
- One patch expanded the base font stack to include system fallbacks and set `font-synthesis: none`.
- The child strategy summary explicitly identifies `font-display: swap` as the mechanism for immediate text paint with fallback fonts.
- The measured evidence set reports 3 improvements across 3 repositories with 100% directional consistency, but no numeric delta values were supplied.

### Inference
- These changes are consistent with reducing first-render font blocking and improving perceived load speed.
- The evidence supports applying the strategy when remote fonts are part of the initial render path and fallback text is acceptable.
- The evidence does not justify claiming a universal percentage improvement or a guaranteed LCP reduction.

### Sources
- `woowacourse/perf-basecamp#177`
- `axone-protocol/docs#730`

## Risks and limitations

- If the font is a strong part of the brand identity, fallback text may briefly appear in a different typeface before swap completes.
- Non-blocking stylesheet loading can require a `noscript` fallback if JavaScript is disabled.
- Preconnect only helps when the remote font origin is actually used.
- This strategy addresses first-render blocking, not all font-related performance issues.
- The evidence does not support claiming browser coverage, universal timing gains, or a specific validation rule beyond the observed mechanisms.