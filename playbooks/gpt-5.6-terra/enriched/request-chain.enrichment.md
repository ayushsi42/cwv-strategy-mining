applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### Parallelize independent lazy module loads while preserving code splitting

When an EDS block needs multiple independent modules, start their imports together rather than awaiting one before discovering the next. This preserves separate bundles while avoiding serial lazy-loading work.

**Bad example:**

```javascript
// EDS: blocks/hero/hero.js
export default async function decorate(block) {
  const { decorate: decorateHero } = await import('./hero-renderer.js');
  const { observeHero } = await import('../../scripts/tracking.js');

  decorateHero(block);
  observeHero(block);
}

// CS/AMS: /apps/my-site/clientlibs/hero/js/hero.js
async function loadClientlib(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.append(script);
  });
}

async function decorateHero(block) {
  await loadClientlib('/etc.clientlibs/my-site/clientlibs/hero-renderer.js');
  await loadClientlib('/etc.clientlibs/my-site/clientlibs/hero-tracking.js');

  window.HeroRenderer.decorate(block);
  window.HeroTracking.observe(block);
}

document.querySelectorAll('.hero').forEach(decorateHero);
```

**Why this is bad:** Parallelizing lazy loading for required dependencies can keep the bundle size as small as possible.

**Good example:**

```javascript
// EDS: blocks/hero/hero.js
export default async function decorate(block) {
  const [
    { decorate: decorateHero },
    { observeHero },
  ] = await Promise.all([
    import('./hero-renderer.js'),
    import('../../scripts/tracking.js'),
  ]);

  decorateHero(block);
  observeHero(block);
}

// CS/AMS: hero component HTL
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='my-site.hero'}"></sly>

<div class="hero" data-sly-resource="${'hero' @ resourceType='my-site/components/hero'}"></div>
```

```xml
<!-- CS/AMS: /apps/my-site/clientlibs/hero/.content.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[my-site.hero]"
          allowProxy="{Boolean}true"/>
```

```javascript
// CS/AMS: /apps/my-site/clientlibs/hero/js/hero.js
function loadClientlib(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.append(script);
  });
}

async function decorateHero(block) {
  await Promise.all([
    loadClientlib('/etc.clientlibs/my-site/clientlibs/hero-renderer.js'),
    loadClientlib('/etc.clientlibs/my-site/clientlibs/hero-tracking.js'),
  ]);

  window.HeroRenderer.decorate(block);
  window.HeroTracking.observe(block);
}

document.querySelectorAll('.hero').forEach(decorateHero);
```

Use this only when the modules have no initialization-order dependency. Keep dependent imports ordered, and defer non-critical modules until they are needed.

> **Source PRs** — **approach:** scalableminds/webknossos#5993, konturio/disaster-ninja-fe#344, decentraland/js-sdk-toolchain#549, digitalfabrik/integreat-app#942, elastic/kibana#161144 · **anti-pattern:** platform-q-ai/jarga-admin#79, vorausrobotik/vdoc#128