applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### Fix 4: Serve local fonts with `font-display: swap`

Serve fonts from local static assets and use `font-display: swap`.

```css
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: local('Inter'), url('/inter.woff2') format('woff2');
}

body {
  font-family: 'Inter', system-ui, sans-serif;
}
```

Preload the locally served font when appropriate:

```html
<link rel="stylesheet" href="/fonts.css" />
<link rel="preload" crossorigin href="/inter.woff2" as="font" />
```

**Why:** the evidence shows replacing externally loaded Google Fonts with a local font stylesheet and `font-display: swap`. Another source PR changed `font-display: block` to `swap` across font-face declarations; its audit described `block` as hiding text while the custom font downloads.

Where supported by the font files and site content, consider importing only the character sets needed by the site.

> **Source PRs** — **approach:** mumendiraneyya/clinic_website#23, UMAprotocol/website#128, gnolang/www.gno.land#9, MariaBraganca/ban-berlinarchnet#250, boostcampwm-2021/WEB23-HyupUp#165 · **anti-pattern:** lifeisbeautifu1/modern-react-app#61