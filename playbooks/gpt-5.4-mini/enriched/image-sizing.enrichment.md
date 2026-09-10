### Global image reset

**Bad example:**
```scss
img {
  font-style: italic;
  background-repeat: no-repeat;
  background-size: cover;
  shape-margin: 1rem;
  max-width: 100%;
  height: auto;
  vertical-align: middle;
}
```

**Why this is bad:** A blanket `img` reset can unintentionally change every image on the site, including components that rely on different sizing, alignment, or object-fit behavior. It also mixes presentation concerns into a global rule, making it harder to reason about which images are reserving space for CLS and which are being styled for other reasons. Prefer component-scoped image sizing rules or explicit `width` / `height` attributes on the markup that emits the image.

**Good example:**
```scss
.hero__image {
  max-width: 100%;
  height: auto;
  vertical-align: middle;
}
```

> **Source PRs** — **approach:** woowacourse/perf-basecamp#163, technologiestiftung/service-agentinnen#34, technologiestiftung/service-agentinnen#27, guardian/dotcom-rendering#4742, mozilla/bedrock#11994 · **anti-pattern:** felix-berlin/webshaped-blog-astro#64