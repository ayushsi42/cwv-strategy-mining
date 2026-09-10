### Lazy-load heavy feature components behind user intent

When a feature is only needed after a user opens a tab, dialog, or advanced flow, keep its code out of the initial bundle and load it on demand.

```js
// Good — EDS block decorate() loads the heavy feature only when needed
export default function decorate(block) {
  const openBtn = block.querySelector('[data-geo-open]');
  const modalHost = block.querySelector('[data-geo-modal-host]');

  openBtn?.addEventListener('click', async () => {
    const { default: GeoModal } = await import('./geo-modal.js');
    GeoModal.mount(modalHost);
  });
}
```

This can keep code out of the initial bundle for users who never open the feature, while still allowing the feature to initialize normally once they opt in.

> **Source PRs** — **approach:** edbpede/feedback#3, ibenian/algebench#123, 3DStreet/3dstreet#540, elastic/kibana#198240, ustaxcourt/ef-cms#5980 · **anti-pattern:** kamiazya/web-csv-toolbox#551, Ferlab-Ste-Justine/ferlab-ui#513