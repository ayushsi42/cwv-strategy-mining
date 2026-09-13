## Preload font URLs that match the `@font-face` source

Preload font files from the document head when they are needed early in rendering. The evidence shows font preloads using `as="font"`, an appropriate font MIME type, and `crossorigin="anonymous"`, alongside matching `@font-face` declarations.

### Anti-pattern: preload a different URL than the font-face source

```html
<link rel="preload"
      href="/fonts/brand-regular.woff2"
      as="font"
      type="font/woff2"
      crossorigin="anonymous">
```

```css
@font-face {
  font-family: "Brand";
  src: url("/assets/brand-regular.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
}
```

**Why this is bad:** the preload URL does not match the URL in the `@font-face` declaration. Use the same font-file URL for both.

### Approach: declare and preload the same font files

```css
@font-face {
  font-family: "Brand";
  src: url("/fonts/brand-regular.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
}

@font-face {
  font-family: "Brand";
  src: url("/fonts/brand-semibold.woff2") format("woff2");
  font-weight: 600;
  font-style: normal;
}
```

```html
<link rel="preload"
      href="/fonts/brand-regular.woff2"
      as="font"
      type="font/woff2"
      crossorigin="anonymous">

<link rel="preload"
      href="/fonts/brand-semibold.woff2"
      as="font"
      type="font/woff2"
      crossorigin="anonymous">
```

Keep the preload URLs aligned with the font URLs used by the emitted `@font-face` declarations.

> **Source PRs** — **approach:** htmlacademy-adaptive/2280491-cat-energy-28#9, jakearchibald/svgomg#339, voorhoede/head-start#209, mongodb/snooty#1050