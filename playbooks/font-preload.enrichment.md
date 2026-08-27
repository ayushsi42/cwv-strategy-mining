### Preload a single stable font from a dedicated CSS file

```html
<link rel="stylesheet" href="/fonts.css" />
<link rel="preload" href="/inter.woff2" as="font" crossorigin />
```

```css
@font-face {
  font-display: swap;
  font-family: Inter;
  font-style: normal;
  font-weight: 100 900;
  src:
    local(inter),
    url("inter.woff2") format("woff2");
}
```

Use this when the font file URL is stable and the font is already isolated in its own stylesheet. Keeping the `@font-face` in a dedicated CSS file makes the preload target explicit and easy to keep aligned with the actual font URL.

#### Good example

```html
<link rel="stylesheet" href="/fonts.css" />
<link rel="preload" href="/inter.woff2" as="font" crossorigin />
```

```css
@font-face {
  font-display: swap;
  font-family: "Inter";
  font-style: normal;
  font-weight: 100 900;
  src: local("Inter"), url("inter.woff2") format("woff2");
}
```