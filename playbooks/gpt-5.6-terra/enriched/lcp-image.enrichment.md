applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### Opt-in LCP mode for reusable image components

When a reusable image component normally lazy-loads images, expose an explicit eager or above-the-fold variant. Apply it to the image that is rendered above the fold or is identified as the LCP image; keep the component default lazy for other images.

```html
<!-- Good: output for an above-the-fold or LCP image -->
<img src="hero.jpg"
     alt="Hero"
     fetchpriority="high"
     loading="eager">
```

Configure the variant in the page template or component instance that renders the relevant image. The evidence shows reusable profile-image components retaining lazy loading by default while allowing specific instances to load eagerly.

### Making every shared-component image eager and high priority

```html
<!-- Bad -->
<img src="card-image.jpg"
     alt="Card image"
     fetchpriority="high"
     loading="eager">
```

**Why this is bad:** The evidence supports eager loading for above-the-fold images while retaining lazy loading as the default for reusable image components. Applying eager loading and high priority to every shared-component image does not preserve that distinction.

> **Source PRs** — **approach:** codeit-bootcamp-frontend/Weekly-Mission#104, dailydotdev/apps#2470, eCOO-FURG/apps#167, woowacourse/perf-basecamp#117, woowacourse/perf-basecamp#176 · **anti-pattern:** oreoorbitz/Dawn-employee-modifcations#2