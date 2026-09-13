### Fix 1: Add `font-display: swap` to every custom `@font-face`

```css
/* Good */
@font-face {
  font-family: 'Source Sans Pro';
  src: url('/assets/sourcesanspro-regular-webfont.woff2') format('woff2');
  font-display: swap;
}

@font-face {
  font-family: 'Source Sans Pro';
  src: url('/assets/sourcesanspro-bold-webfont.woff2') format('woff2');
  font-weight: 700;
  font-display: swap;
}
```

**Precondition:** any custom `@font-face` in repo CSS is missing an explicit `font-display` value.

**Bad example:**
```css
@font-face {
  font-family: 'Source Sans Pro';
  src: url('/assets/sourcesanspro-regular-webfont.woff2') format('woff2');
}
```

**Why this is bad:** the audit flagged `font-display: block` as a performance issue. Using `swap` allows text to render while the custom font loads, instead of hiding it for a period of time.

### Add a web-safe fallback before the generic family in every `font-family` stack

```css
/* Good */
body {
  font-family: 'Source Sans Pro', Arial, sans-serif;
}

h1, h2, h3 {
  font-family: 'Source Sans Pro', 'Helvetica Neue', Arial, sans-serif;
}
```

**Precondition:** any `font-family` declaration that uses a custom font is missing a web-safe fallback before the generic family.

**Bad example:**
```css
body {
  font-family: 'Source Sans Pro', sans-serif;
}
```

**Why this is bad:** if the custom font fails to load or is delayed, the browser has fewer fallback options immediately available, which can contribute to a less stable visual experience.

### Add `size-adjust` only when font metric data is available

```css
/* Good */
@font-face {
  font-family: 'Source Sans Pro Fallback';
  src: local('Arial');
  size-adjust: 102%;
  ascent-override: 92%;
  descent-override: 24%;
  line-gap-override: 0%;
}

body {
  font-family: 'Source Sans Pro', 'Source Sans Pro Fallback', Arial, sans-serif;
}
```

**Precondition:** metric data is available for the custom font and no size-adjusted fallback exists yet.

**Bad example:**
```css
@font-face {
  font-family: 'Source Sans Pro Fallback';
  src: local('Arial');
  size-adjust: 102%;
}
```

**Why this is bad:** `size-adjust` is intended to help align fallback metrics, but by itself it does not include the other metric overrides that can help reduce layout shift.

### Preload critical font files only when the font is already needed for initial render

```html
<head>
  <link rel="preload" href="/assets/sourcesanspro-regular-webfont.woff2" as="font" type="font/woff2" crossorigin="anonymous" />
  <link rel="preload" href="/assets/sourcesanspro-bold-webfont.woff2" as="font" type="font/woff2" crossorigin="anonymous" />
</head>
```

**Precondition:** the page uses a custom font on above-the-fold text and the font is already known to be needed for the initial render.

**Bad example:**
```html
<head>
  <link rel="preload" href="/assets/sourcesanspro-regular-webfont.woff2" as="font" type="font/woff2" crossorigin="anonymous" />
</head>
```

**Why this is bad:** preloading fonts that are not needed for the initial render can waste bandwidth and compete with more important resources. It should be reserved for fonts that are already on the critical path, such as LCP headings or hero copy.

> **Source PRs** — **approach:** mumendiraneyya/clinic_website#23, cfpb/hmda-frontend#2180, MariaBraganca/ban-berlinarchnet#250, adobe/spectrum-hub#22, cplprince/kingdoms#6