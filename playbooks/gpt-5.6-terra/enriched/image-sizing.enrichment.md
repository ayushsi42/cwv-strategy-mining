applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams', 'headless']

### Sizing only in a stylesheet

```html
<!-- Bad — HTL emits an unsized image and relies on a clientlib stylesheet -->
<img class="cmp-header__logo"
     src="${logo.path @ context='uri'}"
     alt="${logo.alt}">
```

```css
/* clientlib-site.css */
.cmp-header__logo {
  width: 202px;
  height: 58px;
}
```

**Why this is bad:** The browser can parse and lay out the `<img>` before the clientlib CSS has loaded and applied, so it may not reserve the logo’s space immediately.

```html
<!-- Good — emit the real intrinsic dimensions in HTL -->
<img class="cmp-header__logo"
     src="${logo.path @ context='uri'}"
     width="202"
     height="58"
     alt="${logo.alt}">
```

```css
/* Use CSS only for responsive presentation */
.cmp-header__logo {
  max-width: 100%;
  height: auto;
}
```

> **Source PRs** — **approach:** amfoss/events-portal#10, mozilla/bedrock#11994, utmgdsc/website#41, BrightonMboya/tazama#4, codeit-bootcamp-frontend/8-Sprint-Mission#265 · **anti-pattern:** nearform/bioconductor.org#47, lensterxyz/lenster#1265