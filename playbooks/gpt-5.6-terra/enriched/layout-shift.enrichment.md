### Keep async controls mounted while their settings resolve

When an async setting determines whether a control is enabled, consider rendering the control in its final location immediately and using its disabled state as the loading state. Leaving the block empty and inserting the control after the request completes can push following content when it appears.

```js
// blocks/key-metrics/key-metrics.js (EDS)
export default async function decorate(block) {
  block.innerHTML = `
    <label class="key-metrics-toggle">
      <input type="checkbox" disabled aria-describedby="key-metrics-status">
      <span>Enable Key Metrics</span>
    </label>
    <p id="key-metrics-status" class="key-metrics-status">Loading settings…</p>
  `;

  const input = block.querySelector('input');
  const status = block.querySelector('.key-metrics-status');

  const response = await fetch('/api/key-metrics-settings');
  const settings = await response.json();

  input.checked = Boolean(settings.enabled);
  input.disabled = false;
  status.textContent = '';
}
```

```css
/* Preserve the loading-status footprint after its text is cleared. */
.key-metrics-status {
  min-height: 1.5rem;
}
```

A similar approach can be used for loading cards, result panels, and image regions: render a skeleton or reserved container, then replace its contents when data arrives.

### Conditionally inserting an async control after data arrives

```js
// Bad — the block is empty at first paint, then grows when settings resolve.
export default async function decorate(block) {
  block.replaceChildren();

  const response = await fetch('/api/key-metrics-settings');
  const settings = await response.json();

  block.innerHTML = `
    <label>
      <input type="checkbox" ${settings.enabled ? 'checked' : ''}>
      <span>Enable Key Metrics</span>
    </label>
  `;
}
```

**Why this is bad:** The initial empty block has no control footprint. Inserting the toggle after the delayed request can push following content downward and contribute to CLS. Render the disabled control or a same-sized placeholder at first paint, then update its state when the request resolves.

> **Source PRs** — **approach:** amfoss/events-portal#10, redpanda-data/console#2043, utmgdsc/website#41, RolnickLab/ami-platform#186, RedHat-UX/red-hat-design-system#2043 · **anti-pattern:** google/site-kit-wp#6718, scaffold-eth/scaffold-eth-2#924, aemsites/stericycle-shared#445, atlassian/landkid#169