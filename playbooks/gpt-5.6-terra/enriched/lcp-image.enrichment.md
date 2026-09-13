### Marking every above-the-fold image as high priority

```html
<!-- Bad: multiple images receive high priority -->
<img src="hero.jpg"
     alt="Hero"
     fetchpriority="high"
     loading="eager"
     width="1200"
     height="800">

<img src="card-1.jpg"
     alt="Featured article"
     fetchpriority="high"
     loading="eager"
     width="640"
     height="360">

<img src="card-2.jpg"
     alt="Featured article"
     fetchpriority="high"
     loading="eager"
     width="640"
     height="360">
```

**Why this is bad:** This does not match the targeted priority patterns shown in the evidence. The PRs apply priority to a hero image identified as LCP, or pass priority to the first image in a collection layout rather than assigning it to every collection image.

Target priority deliberately for the image that is expected to be the page's LCP image, and validate the choice for the relevant template.

```html
<!-- Good: the hero image receives high priority -->
<img src="hero.jpg"
     alt="Hero"
     fetchpriority="high"
     loading="eager"
     width="1200"
     height="800">

<img src="card-1.jpg"
     alt="Featured article"
     width="640"
     height="360">

<img src="card-2.jpg"
     alt="Featured article"
     loading="lazy"
     width="640"
     height="360">
```

> **Source PRs** — **approach:** woowacourse/perf-basecamp#117, woowacourse/perf-basecamp#176, cloudflare/telescope#155, lsst-epo/rubin-obs-client#573, digitalgroundgame/pragmatic-papers#491 · **anti-pattern:** masumi-network/sokosumi#42