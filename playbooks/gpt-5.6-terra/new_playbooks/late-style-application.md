---
issue_type: late-style-application
applicable_flavors:
- cs
- ams
risk_tier: high
required_validation:
- affected_template_and_component_scope_identified
- late_style_arrival_confirmed_in_render_trace
- critical_css_rules_minimized_to_affected_initial_output
forbidden_techniques: []
source_prs:
- carmentacollective/carmenta#441
- danskernesdigitalebibliotek/dpl-cms#230
- Automattic/newspack-blocks#1548
- GenesisEducationKyiv/front-end-school-3-0-vlad0syk#11
---
# Late style application

> **Risk tier:** high · **CWV metric:** FCP, LCP, CLS

## What this addresses

Late-arriving CSS can expose an unstyled page background or allow components to render with temporary geometry before their stylesheet applies. Rendering critical style rules in the initial HTML can prevent a flash of unstyled content and reduce layout shift caused by stylesheet arrival.

## When to apply / when to skip
**Apply when:**
- A filmstrip, WebPageTest trace, or Lighthouse evidence shows a visible flash of the default background, unstyled content, or changing component geometry after initial markup paints.
- The affected page template and head output path are known.
- The rules needed for the affected initial output can be identified.

**Skip when:**
- The visual change is caused by late image dimensions, asynchronous content, font swapping, or a third-party overlay rather than CSS arrival.
- The affected style is editor-only or not present in the rendered page output.

## Recommended approaches

### Inline a minimal template-specific visual baseline

Place the rules needed to paint the document background and stabilize the affected initial template output in the page head. Keep remaining styling in the normal stylesheet path.

```html
<!-- Good: /apps/example/components/structure/page/head.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html" />
<sly data-sly-use.page="com.example.core.models.PageModel" />

<style data-sly-test="${page.landingPage}">
  html,
  body {
    margin: 0;
    background: #f7f5f2;
  }

  .cmp-hero {
    min-height: 32rem;
    background: #1d3d5a;
  }

  .cmp-hero__content {
    max-width: 75rem;
    margin: 0 auto;
    padding: 2rem 1rem;
  }
</style>

<sly data-sly-call="${clientlib.css @ categories='example.site.landing'}" />
```

```xml
<!-- Good: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/clientlib-site-landing/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          xmlns:cq="http://www.day.com/jcr/cq/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.site.landing]"
          dependencies="[example.site.base]"/>
```

The inline rules establish the initial visual baseline while the landing-page stylesheet continues to provide the remaining styles.

### Reserve the initial component shell in server-rendered markup

Use stable server-rendered classes and dimensions for an affected component so its shell is available before its complete stylesheet applies.

```html
<!-- Good: /apps/example/components/content/hero/hero.html -->
<sly data-sly-use.hero="com.example.core.models.HeroModel" />

<section class="cmp-hero"
         data-sly-test="${hero.image}"
         aria-labelledby="hero-title">
  <div class="cmp-hero__content">
    <h1 id="hero-title" class="cmp-hero__title">${hero.title}</h1>
    <p class="cmp-hero__summary" data-sly-test="${hero.summary}">
      ${hero.summary}
    </p>
  </div>
</section>
```

```html
<!-- Good: minimal matching rules in the page head -->
<style>
  .cmp-hero { min-height: 32rem; }
  .cmp-hero__content { max-width: 75rem; margin: 0 auto; padding: 2rem 1rem; }
</style>
```

The server-rendered shell and matching initial rules can reduce movement caused by later stylesheet application.