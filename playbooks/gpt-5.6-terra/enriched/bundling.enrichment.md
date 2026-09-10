applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### EDS: conditionally load authored-content renderers

```javascript
// Load renderer modules only when this block contains matching content
export default async function decorate(block) {
  const mermaidNodes = block.querySelectorAll('pre code.language-mermaid');
  const codeNodes = block.querySelectorAll(
    'pre code[class*="language-"]:not(.language-mermaid)',
  );

  if (mermaidNodes.length) {
    const { renderMermaid } = await import('./mermaid.js');
    await renderMermaid(mermaidNodes);
  }

  if (codeNodes.length) {
    const { highlightCode } = await import('./highlight-code.js');
    highlightCode(codeNodes);
  }
}
```

Keep Mermaid and syntax-highlighting renderers in standalone modules.

> **Source PRs** — **approach:** ant-design/x#1402, exelearning/exelearning#1439, nader-eloshaiker/screen-geometry-app#508, woowacourse/perf-basecamp#154, woowacourse/perf-basecamp#163 · **anti-pattern:** Jujulego/palantir#241, ministryofjustice/hmpps-content-hub-ui#65, dailydotdev/apps#1426, newrelic/newrelic-browser-agent#532