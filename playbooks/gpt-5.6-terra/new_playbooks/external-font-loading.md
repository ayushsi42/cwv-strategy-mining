---
issue_type: external-font-loading
applicable_flavors:
- cs
risk_tier: medium
required_validation: []
forbidden_techniques: []
source_prs:
- codeit-fe16-part4-team1/project-mogazoa-app#84
- vercel/next.js#43482
- SeeYouThursday/SeeYouThursdayInc#97
- YAPP-Github/25th-Web-Team-2-FE#11
---
# External font loading

> **Risk tier:** medium · **Applies to:** CS · **CWV metric:** CLS

## What this addresses

Externally hosted font CSS and font files introduce an external dependency for font loading. The evidence shows that locally hosted, subsetted WOFF2 fonts used through Next.js font tooling can avoid external font requests and support font-loading optimization. Next.js font tooling is also described in the evidence as helping prevent CLS.

## When to apply / when to skip
**Apply when:**
- A network trace identifies externally hosted font CSS or font files.
- The page uses a known set of font families, weights, styles, and language glyph ranges.
- The font license permits self-hosting.
- The font files can be subsetted to the glyph ranges the site requires.

**Skip when:**
- The font license prohibits bundling or self-hosting the font files.
- The site needs language coverage that cannot safely be represented by the available subsets.
- Replacing the font would change regulated, brand-approved, or localized typography without design approval.

## Recommended approaches

### Self-host only the WOFF2 faces that are used

Use locally hosted, subsetted WOFF2 files and declare the weights and styles used by the application. The evidence shows projects using local subsetted WOFF2 files with `next/font/local` rather than external font providers.

```css
/* clientlibs/site/fonts/css/fonts.css */
@font-face {
  font-family: "Pretendard";
  src: url("../resources/fonts/Pretendard-Regular.subset.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Pretendard";
  src: url("../resources/fonts/Pretendard-SemiBold.subset.woff2") format("woff2");
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Pretendard";
  src: url("../resources/fonts/Pretendard-Bold.subset.woff2") format("woff2");
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

body {
  font-family: "Pretendard", sans-serif;
}
```

Use only the required weights and styles. The evidence specifically identifies subsetted WOFF2 files as a way to minimize font-file size.

### Use framework font tooling where available

For Next.js applications, use `next/font/local` for local font files or `next/font/google` for supported Google fonts. The evidence shows `next/font` being used to generate font CSS and apply generated font classes or variables to the document layout.

```html
<sly
  data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
  data-sly-call="${clientlib.css @ categories='site.fonts'}">
</sly>

<html lang="en" class="brand-font">
  <body>
    <sly data-sly-resource="${'root' @ resourceType='wcm/foundation/components/responsivegrid'}"></sly>
  </body>
</html>
```

The evidence describes Next.js as generating font-related CSS during the build and applying the generated class to the HTML document.

### Verify the fonts used by the initial layout

Confirm that the locally hosted font files include the weights and styles used by initial page content. The evidence includes projects defining only the font weights used by their typography.

## Anti-patterns

### Importing font CSS from an external provider

```css
/* Bad: external font CSS depends on a third-party provider */
@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@100;300;400;500;600;700;800;900&display=swap");

body {
  font-family: "Poppins", sans-serif;
}
```

**Why this is bad:** this retains an external dependency for font loading. The evidence shows projects replacing Google Fonts CSS imports with `next/font/google` or locally hosted fonts.

### Loading more font weights than the application uses

```css
/* Bad: declares many weights without confirming that they are used */
@font-face {
  font-family: "Acme Sans";
  src: url("../resources/fonts/acme-sans-thin.woff2") format("woff2");
  font-weight: 100;
}

@font-face {
  font-family: "Acme Sans";
  src: url("../resources/fonts/acme-sans-black.woff2") format("woff2");
  font-weight: 900;
}
```

**Why this is bad:** the evidence recommends using subsetted WOFF2 files and shows implementations limited to the weights used by the application.