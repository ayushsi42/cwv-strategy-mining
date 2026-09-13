### Don't rely on non-critical CSS for image dimensions

```html
<!-- Bad: component.html -->
<img class="site-header__logo"
     src="${properties.logo @ context='uri'}"
     alt="${properties.logoAlt}">
```

```css
/* clientlib-site-header/css/header.css, loaded after initial render */
.site-header__logo {
  width: 202px;
  height: 58px;
}
```

**Why this is bad:** The browser may encounter the `<img>` before its CSS is available. Providing dimensions only in CSS can mean the image’s size changes after the stylesheet loads, potentially contributing to layout shift in surrounding header content.

Put `width` and `height` attributes on the emitted `<img>` element. CSS can still control responsive rendering.

```html
<!-- Good: component.html -->
<img class="site-header__logo"
     src="${properties.logo @ context='uri'}"
     width="202"
     height="58"
     alt="${properties.logoAlt}">
```

> **Source PRs** — **approach:** amfoss/events-portal#10, mozilla/bedrock#11994, utmgdsc/website#41, BrightonMboya/tazama#4, codeit-bootcamp-frontend/8-Sprint-Mission#265 · **anti-pattern:** nearform/bioconductor.org#47, lensterxyz/lenster#1265