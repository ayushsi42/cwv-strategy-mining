### Preload late-discovered localization form assets

When a localization form or selector is discovered late in the document, preload its critical CSS so the browser can fetch it in parallel with HTML parsing.

```html
<!-- Good -->
<link rel="preload" href="/assets/component-localization-form.css" as="style">
<link rel="stylesheet" href="/assets/component-localization-form.css">
```

Use this only when the stylesheet is on the critical render path and is not already discovered early in `<head>`.