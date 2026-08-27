### Add `loading="lazy"` to below-the-fold images

**Apply when** the image is clearly below the fold or not part of the LCP critical chain, such as article cards, client logos, and footer ads.

```html
<!-- Good — non-LCP images in lists / cards / footers can be lazy-loaded -->
<img
  loading="lazy"
  src="{{ .Params.image | absURL }}"
  alt=""
  class="rounded-t-xl object-cover"
  style="height:212px; width:100%"
>
```

**Do not apply** `loading="lazy"` to the LCP image or any image that must load during the critical render path.

```html
<!-- Bad — the hero/LCP image is delayed by lazy-loading -->
<img
  loading="lazy"
  src="https://cdn.example.com/hero.jpg"
  alt="Hero banner"
  width="1600"
  height="900"
>
```

**Why this is bad:** `loading="lazy"` delays the browser’s request for the image until it is near the viewport. If the image is part of the LCP critical chain, lazy-loading can worsen LCP.

Use `loading="lazy"` only for non-critical images.

> **Source PRs** — **approach:** nypublicradio/gothamist-vue3#66, rotationalio/rotational.io#414, aemdemos/gabrielpoalelungi-cola-sta#92