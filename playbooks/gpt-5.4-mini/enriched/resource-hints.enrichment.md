### Preconnect to the LCP image CDN origin

```html
<!-- Good — the LCP image is served from a separate cross-origin image host -->
<link rel="preconnect" href="https://s3.ap-northeast-2.amazonaws.com" crossorigin>
```

Use this when the LCP image is hosted on a different origin than the HTML. `preconnect` can help the browser start the connection setup earlier for that origin, and `crossorigin` is included for cross-origin reuse.

> **Source PRs** — **approach:** earlman/me-dev#13, AzureAD/microsoft-authentication-library-for-js#6550, nypublicradio/gothamist-vue3#66, rotationalio/rotational.io#414, SOPT-all/37-COLLABORATION-WEB-IDUS#90