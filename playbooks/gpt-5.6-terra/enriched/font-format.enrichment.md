### Use WOFF2 and `font-display: swap` for self-hosted fonts

```css
/* Avoid — TTF source */
@font-face {
  font-family: 'Brand Display';
  src: url('/fonts/brand-display.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
}
```

**Why this is bad:** The evidence review notes that using a TTF file resulted in a substantially lower Lighthouse performance score than WOFF2, and requests `font-display: swap`.

```css
/* Use — shared stylesheet */
@font-face {
  font-family: 'Brand Display';
  src: url('/fonts/brand-display.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

/* Block or component stylesheet */
.auth .auth-title {
  font-family: 'Brand Display', sans-serif;
}
```

Define the self-hosted font face in a shared stylesheet and use the font family from block and component styles.

> **Source PRs** — **approach:** FRONTENDSCHOOL10/Haemadi#103