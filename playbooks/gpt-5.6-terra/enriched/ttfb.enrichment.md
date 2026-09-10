applicable_flavors for the playbook this content is being added to: ['cs', 'ams']

### Split optional client libraries from the site-wide bundle (CS/AMS)

Split optional dependencies out of the site-wide bundle to reduce main-bundle size.

```xml
<!-- Bad — apps/site/clientlibs/clientlib-base/.content.xml -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.base]"
    embed="[site.feature.chart]"
    allowProxy="{Boolean}true"/>
```

**Why this is bad:** The chart dependency is embedded in `site.base`, so it is included wherever `site.base` is loaded. Including optional dependencies in the main bundle can increase main-bundle size.

```xml
<!-- Good — apps/site/clientlibs/clientlib-chart/.content.xml -->
<jcr:root
    xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.feature.chart]"
    allowProxy="{Boolean}true"/>
```

```html
<!-- Good — apps/site/components/chart/chart.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='site.feature.chart'}"></sly>

<div class="cmp-chart" data-chart-config="${model.config}"></div>
```

Load the feature category from the component or template that requires it rather than embedding `site.feature.chart` in the global `site.base` category.

> **Source PRs** — **approach:** ls1intum/Artemis#5322, metabase/shoppy#71, nautobot/nautobot#7165, next-step/infra-subway-monitoring#595, shopware/frontends#309