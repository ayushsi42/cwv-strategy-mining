### Split feature-heavy components into standalone modules

When a page only needs a small core surface, move optional or heavyweight features into separate modules so the default code path stays lean. This is especially useful when a single feature has a large base implementation plus optional add-ons like syntax highlighting, diagram rendering, or other feature-specific renderers.

```javascript
// Good — keep the default module small, and load optional features only when needed
export default async function decorate(block) {
  const codeBlocks = block.querySelectorAll('pre code');

  if (!codeBlocks.length) return;

  const { highlightAll } = await import('./highlight-code.js');
  highlightAll(codeBlocks);
}
```

This can keep the main entrypoint from pulling in feature code that many pages never use, while still allowing the feature to load when needed.

> **Source PRs** — **approach:** ant-design/x#1402, codecov/gazebo#3738, nader-eloshaiker/screen-geometry-app#508, helius-labs/helius-sdk#207, sam-goodwin/itty-aws#62 · **anti-pattern:** n8n-io/n8n#25649, getsentry/sentry#83982, felix-berlin/webshaped-blog-astro#65, mui-org/material-ui-x#2395