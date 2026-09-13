### Additional optimization: Subset web fonts to the character ranges the site serves

When a font family contains glyphs for scripts the site does not use, serve a subset rather than the full font file. This can reduce font transfer size.

```css
/* Bad: ships a full multi-script font when the site serves Latin-only content */
@font-face {
  font-family: 'Brand';
  src: url('./fonts/brand-full.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
```

**Why this is bad:** The site may download font data for characters it does not render.

```css
/* Good: serve a Latin subset when it covers the site's content */
@font-face {
  font-family: 'Brand';
  src: url('./fonts/brand-latin.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

body {
  font-family: 'Brand', Arial, system-ui, sans-serif;
}
```

**Precondition:** The subset covers the content the site serves.

**Do not apply when:** Pages require glyphs that are not included in the subset. Use font files that provide the required glyph coverage.

> **Source PRs** — **approach:** mumendiraneyya/clinic_website#23, UMAprotocol/website#128, gnolang/www.gno.land#9, MariaBraganca/ban-berlinarchnet#250, boostcampwm-2021/WEB23-HyupUp#165 · **anti-pattern:** lifeisbeautifu1/modern-react-app#61