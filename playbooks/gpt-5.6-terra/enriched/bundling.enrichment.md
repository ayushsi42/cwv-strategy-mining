### EDS: load optional block features only when authored markup requires them

Keep optional renderers—such as diagrams, syntax highlighting, or notification integrations—out of the block’s static import graph. Check for the authored feature first, then dynamically import its standalone module.

```javascript
// blocks/article/article.js
export default async function decorate(block) {
  const diagram = block.querySelector('[data-diagram="mermaid"]');

  if (!diagram) {
    return;
  }

  const { renderDiagram } = await import('./mermaid.js');
  await renderDiagram(diagram);
}
```

This can keep the base block module smaller for pages that use the block without the optional feature. Keep the optional implementation in a separate module so that it can be loaded independently.

### Static imports of conditionally used feature modules

```javascript
// Bad — mermaid.js and its dependencies are statically imported whenever this block module loads
import { renderDiagram } from './mermaid.js';

export default async function decorate(block) {
  const diagram = block.querySelector('[data-diagram="mermaid"]');

  if (diagram) {
    await renderDiagram(diagram);
  }
}
```

**Why this is bad:** The condition controls whether the renderer is called, but the module remains a static import. The evidence recommends using dynamic imports to reduce bundle size and shows Mermaid and syntax-highlighting functionality being moved into standalone components as part of a bundle-size improvement. Check for the authored feature before using `import()` to load its standalone module.

> **Source PRs** — **approach:** ant-design/x#1402, exelearning/exelearning#1439, nader-eloshaiker/screen-geometry-app#508, woowacourse/perf-basecamp#154, woowacourse/perf-basecamp#163 · **anti-pattern:** Jujulego/palantir#241, ministryofjustice/hmpps-content-hub-ui#65, dailydotdev/apps#1426, newrelic/newrelic-browser-agent#532