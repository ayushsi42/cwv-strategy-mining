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

Externally hosted font CSS and font files introduce an external dependency for font loading. Locally hosted, subsetted WOFF2 fonts delivered through AEM client libraries avoid external font requests and support predictable font loading. Declaring the required font faces locally can also help prevent layout shifts caused by late font loading.

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

Use locally hosted, subsetted WOFF2 files and declare the weights and styles used by the application.

```css
/* /apps/my-site/clientlibs/site-fonts/css/fonts.css */
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

Use only the required weights and styles. Subsetted WOFF2 files minimize font-file size.

### Load local font CSS through an AEM client library

Create a client library category for the local font CSS and include that category from the page component.

```xml
<!-- /apps/my-site/clientlibs/site-fonts/.content.xml -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.fonts]"
    allowProxy="{Boolean}true"/>
```

```text
# /apps/my-site/clientlibs/site-fonts/css.txt
css/fonts.css
```

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

The client library delivers the locally declared `@font-face` rules with the page rather than requesting font CSS from a third-party provider.

### Verify the fonts used by the initial layout

Confirm that the locally hosted font files include the weights and styles used by initial page content. Define only the font weights used by the site's typography.

## Anti-patterns

### Importing font CSS from an external provider

```css
/* Bad: external font CSS depends on a third-party provider */
@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@100;300;400;500;600;700;800;900&display=swap");

body {
  font-family: "Poppins", sans-serif;
}
```

**Why this is bad:** this retains an external dependency for font loading. Replace external Google Fonts CSS imports with locally hosted font files declared in an AEM client library.

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

**Why this is bad:** use subsetted WOFF2 files and limit declarations to the weights used by the application.