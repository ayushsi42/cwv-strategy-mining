applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### Preload a known stylesheet before it is loaded

The evidence PRs preload stylesheet resources and continue to include the stylesheet normally. For example, ScandiPWA preloads its Typekit stylesheet and also loads it with `rel="stylesheet"`.

```html
<link rel="preload" href="https://use.typekit.net/fji5tuz.css" as="style">
<link rel="stylesheet" href="https://use.typekit.net/fji5tuz.css">
```

For a stylesheet with a known URL, add a preload before the code that loads the stylesheet:

```html
<!-- EDS: head.html -->
<link rel="preload" href="/blocks/localization/localization.css" as="style">
<link rel="stylesheet" href="/blocks/localization/localization.css">

<!-- CS/AMS: page or component HTL, before the clientlib include -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"></sly>
<link rel="preload"
      href="/etc.clientlibs/my-site/clientlibs/clientlib-localization.css"
      as="style">
<sly data-sly-call="${clientlib.css @ categories='my-site.localization'}"></sly>
```

The stylesheet still needs to be loaded normally so that its styles are applied.

> **Source PRs** — **approach:** Shopify/dawn#2258, Quansight/ragna#312, scandipwa/scandipwa#3139, phillipc0/WA-DP#113, cfpb/hmda-frontend#2180