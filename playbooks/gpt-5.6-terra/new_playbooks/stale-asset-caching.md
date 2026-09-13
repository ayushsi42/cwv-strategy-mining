---
issue_type: stale-asset-caching
required_validation: []
forbidden_techniques: []
flavor_overrides: {}
applicable_flavors:
- eds
- cs
- ams
risk_tier: medium
source_prs:
- kiwix/libkiwix#712
- ls1intum/Artemis#5322
- rust-lang/rust#101702
- woowacourse-teams/2023-stamp-crush#679
---
# Stale asset caching

## What this addresses

Static JavaScript, CSS, and font files can use immutable caching when their filenames include a hash of their contents. When the file contents change, the generated filename changes as well, allowing the updated asset to be published at a new URL.

## When to apply / when to skip
**Apply when:**
- A performance audit identifies repeat-visit cache misses for static JavaScript, CSS, or font resources.
- The asset publishing process can generate content-fingerprinted filenames and update rendered references to those filenames.
- The affected files are static resources whose URLs can change when their contents change.

**Do not apply until these conditions are resolved:**
- Asset references are assembled dynamically and there is no complete inventory of templates, client code, or CSS `url(...)` references.
- The proposed cache rule would apply immutable caching to URLs whose contents can change without a URL change.

## Recommended approaches

### Publish content-fingerprinted static assets and reference the generated URL

Publish a new URL whenever an asset's bytes change. Keep the fingerprinted filename stable for that asset version, then cache that URL for a long period.

```javascript
// asset-urls.js
// Generated asset references include a content-derived filename.
export const featureIconUrl = new URL(
  './media/feature-icon-4e91c3a8.svg',
  import.meta.url,
).href;
```

```css
/* product-teaser.css */
@font-face {
  font-family: "Brand Sans";
  src: url("./fonts/brand-sans-7bd4a1c0.woff2") format("woff2");
  font-display: swap;
}
```

The fingerprint distinguishes `feature-icon-4e91c3a8.svg` and `brand-sans-7bd4a1c0.woff2` from later versions with different contents.

### Use content hashes in generated bundle filenames

Configure the build to include a content hash in generated bundle filenames.

```javascript
// webpack.common.js
module.exports = {
  output: {
    filename: 'main.[contenthash].js',
  },
};
```

A content hash allows a changed bundle to be emitted under a new filename.

### Update references when generated filenames change

When static filenames include content hashes, update the references that point to those generated files.

```html
<!-- Generated page output references the current content-fingerprinted file. -->
<script src="/assets/site-main-9bc45d11.js"></script>
```

```css
/* Generated CSS references the current content-fingerprinted font file. */
@font-face {
  font-family: "Example Sans";
  src: url("/assets/example-sans-7bd4a1c0.woff2") format("woff2");
}
```

## Anti-patterns

### Long-lived caching for an unversioned asset URL

```html
<!-- Bad: the bytes can change while the URL remains the same. -->
<link rel="stylesheet" href="/assets/site.css">
<script src="/assets/site-main.js"></script>
```

```apache
# Bad: this applies immutable caching to every matching JavaScript and CSS URL.
<LocationMatch "\.(css|js)$">
    Header always set Cache-Control "public, max-age=31536000, immutable"
</LocationMatch>
```

**Why this is bad:** when the URL does not identify a particular content version, an immutable cache policy can retain an older version after deployment.

### Timestamp cache busting on every request

```javascript
// Bad — every page view produces a different URL for identical bytes.
const stylesheet = document.createElement('link');
stylesheet.rel = 'stylesheet';
stylesheet.href = `/assets/theme.css?_=${Date.now()}`;
document.head.append(stylesheet);
```

**Why this is bad:** each timestamp creates a different URL even when the stylesheet contents have not changed, preventing reuse of the same cached URL.

## Flavor-specific notes