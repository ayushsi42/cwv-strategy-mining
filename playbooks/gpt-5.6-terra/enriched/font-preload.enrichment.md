## Example: A preload URL that differs from the CSS font URL

```html
<link rel="preload"
      href="/etc.clientlibs/acme/clientlibs/site/resources/fonts/brand-regular.woff2"
      as="font"
      type="font/woff2"
      crossorigin="anonymous">
```

```css
@font-face {
  font-family: "Brand";
  src: url("/etc.clientlibs/acme/clientlibs/site/resources/fonts/brand-regular-v2.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
}
```

The preload URL and the `@font-face` URL shown here differ. The evidence PRs instead derive preload URLs from the same font asset data used to generate font declarations.

## Approach: Keep the preload and `@font-face` URL aligned

Define the preload and its matching `@font-face` declaration from the same global head injection point when the site permits inline styles.

```html
<!-- /apps/acme/components/structure/page/customheaderlibs.html -->
<sly data-sly-set.fontUrl="/etc.clientlibs/acme/clientlibs/site/resources/fonts/brand-regular.woff2"></sly>

<link rel="preload"
      href="${fontUrl @ context='uri'}"
      as="font"
      type="font/woff2"
      crossorigin="anonymous">

<style>
  @font-face {
    font-family: "Brand";
    src: url("${fontUrl @ context='uri'}") format("woff2");
    font-weight: 400;
    font-style: normal;
  }
</style>
```

The evidence-backed implementation preloads font files in a head component and inlines generated `@font-face` declarations using the same font URLs.

> **Source PRs** — **approach:** woowacourse/perf-basecamp#142, voorhoede/head-start#209, sebastianterleira/astro-spotify-clone#1, unicorn-utterances/unicorn-utterances#1025