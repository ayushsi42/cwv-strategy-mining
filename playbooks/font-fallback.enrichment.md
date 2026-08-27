### Fix 1: Add `font-display: swap` to every custom `@font-face`

```css
/* Good */
@font-face {
  font-family: 'Josefin Sans';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('./fonts/josefin-sans/josefin-sans-400-normal-latin.woff2') format('woff2');
}

@font-face {
  font-family: 'Josefin Sans';
  font-style: italic;
  font-weight: 700;
  font-display: swap;
  src: url('./fonts/josefin-sans/josefin-sans-700-italic-latin.woff2') format('woff2');
}
```

**Precondition:** any custom `@font-face` without an explicit `font-display` value.  
**Risk:** none. `swap` can help avoid invisible text while the web font loads.

### Avoid invalid `font-style` values in `@font-face`

```css
/* Bad */
@font-face {
  font-family: 'Josefin Sans';
  font-style: block;
  font-weight: 400;
  font-display: block;
  src: url('./fonts/josefin-sans/josefin-sans-400-normal-latin.woff2') format('woff2');
}
```

**Why this is bad:** `font-style: block` is not a valid value, so the declaration may be ignored or make the face fail to match as intended. `font-display: block` can hide text for a period while the font loads, which may delay text rendering. Use a valid `font-style` such as `normal` or `italic`, and use `font-display: swap` or `optional` instead.