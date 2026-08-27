---
issue_type: font-delivery--self-host-and-declare-web-fonts-directly
parent_strategy: font-delivery
risk_tier: low
cwv_metrics: [CLS, LCP]
source_prs:
  - codeit-fe16-part4-team1/project-mogazoa-app#84
  - okta/okta-signin-widget#3956
  - woowacourse/perf-basecamp#184
required_validation:
  - local_font_files_present
  - explicit_font_face_rules_present
  - remote_font_stylesheet_removed_or_not_primary
  - body_or_app_font_family_points_to_local_face
forbidden_techniques: []
---

# Self-host and declare web fonts directly

> **Risk tier:** low · **Parent strategy:** font-delivery · **CWV metrics:** CLS, LCP

## Summary

This strategy serves font files from the origin and declares them with explicit `@font-face` rules. The evidence shows local `.woff2` assets added to the repository, CSS/Sass declarations for those assets, and at least one page replacing a remote Google Fonts stylesheet with a local font stylesheet.

This is relevant to:
- **CLS** when font loading causes visible text reflow or swap-related layout movement
- **LCP** when text rendering depends on font availability during the critical render path

The evidence supports the mechanism, not a guaranteed performance outcome. The supplied PRs do not include numeric deltas.

## Mechanism

Observed changes show two concrete patterns:

1. **Local font files are shipped with the app**
   - Example assets: `public/fonts/Cafe24Supermagic-*.woff2`
   - Example assets: `assets/font/inter-latin-*.woff2`
   - Example assets: `public/fonts/josefin-sans/*.woff2`

2. **The shipped fonts are declared directly in CSS**
   - Example: `@font-face` blocks in `public/font.css`
   - Example: `@font-face` blocks in `assets/sass/_fonts.scss`
   - Example: `@font-face` blocks in `.storybook/preview.css`

3. **The app points typography at the local family**
   - Example: `body { font-family: 'Spoqa Han Sans Neo', 'sans-serif'; }`
   - Example: a CSS variable is set to `'Cafe24Supermagic'`
   - Example: local `Josefin Sans` faces are declared for use after replacing the remote stylesheet

## When to apply / when to skip

### Apply when
- Font files are already available or can be added as static assets.
- The current implementation depends on a remote font stylesheet or other external font delivery path.
- You need explicit control over `font-family`, `font-weight`, `font-style`, and `font-display`.
- The affected text participates in initial viewport rendering or other CLS/LCP-sensitive content.

### Skip when
- The font is not part of the critical render path and there is no font-related CWV concern.
- You do not have local font files to serve.
- The font is already self-hosted and explicitly declared, with no delivery-path regression to fix.
- The change would require assuming unsupported browser behavior or inventing delivery details not shown in the evidence.

## Required validation

### local_font_files_present
Confirm that font binaries exist in the repository under a local static path and are referenced from CSS as local files.

**Evidence**
- `public/fonts/Cafe24Supermagic-Regular-v1.0.woff2`
- `public/fonts/Cafe24Supermagic-Bold-v1.0.woff2`
- `assets/font/inter-latin-400-normal.woff2`
- `public/fonts/josefin-sans/josefin-sans-400-normal-latin.woff2`

**What to check**
- The font files are committed to the repo.
- The CSS `src:` values point to those local files.

### explicit_font_face_rules_present
Confirm that one or more `@font-face` blocks declare the shipped family with concrete `src`, `font-weight`, and `font-style` values.

**Evidence**
- `public/font.css`
- `assets/sass/_fonts.scss`
- `.storybook/preview.css`

**What to check**
- Each face has a family name.
- Each face specifies a local file source.
- Weight and style are declared explicitly.
- `font-display` is set where the evidence shows it.

### remote_font_stylesheet_removed_or_not_primary
Confirm that the shipped page no longer relies on a remote font stylesheet as the primary font source, or that any remaining remote import is not the production path being validated.

**Evidence**
- `index.html` replaced Google Fonts `<link>` tags with `/public/font.css`
- `src/app/globals.css` still contains a remote `@import url(//spoqa.github.io/spoqa-han-sans/css/SpoqaHanSansNeo.css);`

**What to check**
- The production route uses the local stylesheet path.
- Any remaining remote import is not the font source that governs the validated render path.
- Do not treat the presence of a remote import anywhere in the repo as proof that the strategy failed.

### body_or_app_font_family_points_to_local_face
Confirm that rendered text uses the locally declared family name in a global or app-level style rule.

**Evidence**
- `body { font-family: 'Spoqa Han Sans Neo', 'sans-serif'; }`
- `:root { --font-cafe24-supermagic: 'Cafe24Supermagic', sans-serif; }`

**What to check**
- The app-level typography references the declared local family.
- The family name used in rendering matches the family name declared in `@font-face`.

## Good examples

### Good: local font file + explicit face + app-level usage
```css
@font-face {
  font-family: 'Josefin Sans';
  font-style: italic;
  font-weight: 400;
  font-display: swap;
  src: url('./fonts/josefin-sans/josefin-sans-400-italic-latin.woff2') format('woff2');
}

body {
  font-family: 'Josefin Sans', sans-serif;
}
```

Why this is supported by the evidence:
- the font file is local,
- the face is declared explicitly,
- the app-level style points to the declared family.

### Good: multiple weights for one local family
```scss
@font-face {
  font-family: 'Inter';
  src: url('../font/inter-latin-600-normal.woff2') format('woff2');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
```

Why this is supported by the evidence:
- the repository ships multiple local Inter weights,
- the Sass file declares them directly,
- the family can be used consistently across weights.

### Good: local font CSS imported into a scoped surface
```ts
import './preview.css';
```

Why this is supported by the evidence:
- the Storybook preview imports a local stylesheet that contains `@font-face` declarations,
- the local font setup is applied to that rendering surface.

## Bad examples

### Bad: remote font stylesheet as the primary delivery path
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Josefin+Sans:ital,wght@0,400;0,700;1,400;1,700&display=swap"
  rel="stylesheet"
/>
```

Why this is a bad fit:
- the evidence shows a local replacement for this pattern,
- the strategy is to self-host and declare the font directly.

### Bad: local files exist but no explicit face declaration
```css
body {
  font-family: 'Cafe24Supermagic', sans-serif;
}
```

Why this is a bad fit:
- the font family is referenced, but the evidence requires explicit `@font-face` rules for shipped files.

## Verification

Use the same CWV metrics that motivated the change and verify on the affected route or surface.

### CLS verification
- Measure whether text shifts are reduced after the local font declaration is applied.
- Compare before/after layout shift traces for the same page state.
- Confirm that fallback-to-webfont swapping no longer produces visible movement in the validated viewport.

### LCP verification
- Measure whether the text-rendering portion of the page becomes available without waiting on the remote font stylesheet.
- Compare before/after LCP timing on the same route and device profile.
- Confirm that the local font path does not block the critical render path.

### Practical checks
- Confirm the font files are served from the origin.
- Confirm the CSS `@font-face` rules resolve to those files.
- Confirm the rendered page uses the intended family name.
- Confirm the production path does not depend on a remote font stylesheet.

## Evidence and confidence

### Observed facts
- One repository replaced remote Google Fonts links with a local stylesheet that declares `@font-face` rules and serves `.woff2` files from the repo.
- Another repository added local font files and declared them in CSS/Sass with explicit weights and `font-display` values.
- A Storybook surface imported a local preview stylesheet that declares local font faces and a font-family variable.
- The supplied evidence associates this strategy with **CLS** and **LCP** signals.

### Inference
- Self-hosting and explicit `@font-face` declarations can reduce dependence on external font delivery and make font loading behavior more predictable.
- The exact CWV effect depends on where the font is used, whether it is critical to initial render, and the chosen `font-display` behavior.

### Source PRs
- `woowacourse/perf-basecamp#184`
- `codeit-fe16-part4-team1/project-mogazoa-app#84`
- `okta/okta-signin-widget#3956`

## Risks and limitations
- A local font strategy can still cause layout shifts if fallback metrics and font metrics are not aligned.
- The evidence includes one repository where a remote font import still appears in a non-primary stylesheet; validation must focus on the actual production font path.
- The supplied PRs do not provide measured deltas, so this playbook cannot promise a fixed CWV improvement.
- This strategy is only justified when the font is part of the affected render path; otherwise it adds asset and maintenance overhead without evidence-backed benefit.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **4 observations across 4 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: font-delivery--self-host-and-declare-web-fonts-directly`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
