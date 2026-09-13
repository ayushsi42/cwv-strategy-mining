### Reserving image dimensions

```html
<img class="post-card__image"
     src="/content/dam/site/images/post-card.jpg"
     alt="Post card image"
     width="300"
     height="300">
```

**Why this matters:** Specifying `width` and `height` reserves space for an image and can help prevent layout shifts.

Use dimensions that are appropriate for the image and its intended layout:

```html
<img class="post-card__image"
     src="/content/dam/site/images/article-hero.jpg"
     alt="Article hero image"
     width="1200"
     height="675">
```

A stylesheet `aspect-ratio` rule can also be used to reserve image space.

> **Source PRs** — **approach:** BrightonMboya/tazama#4, codeit-bootcamp-frontend/8-Sprint-Mission#265, metabase/shoppy#71, codeit-bootcamp-frontend/16-Sprint-Mission#75, processing/p5.js-website#358 · **anti-pattern:** lexisgasa/Blog-UI-TRP#30