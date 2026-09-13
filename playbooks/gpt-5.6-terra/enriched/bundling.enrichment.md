### EDS: load optional interaction features on intent

Do not load optional interaction code during block decoration when it is not needed for the initial render. For pickers, syntax highlighting, diagrams, or advanced configuration, begin loading after the visitor signals likely intent through pointer hover.

```javascript
// Bad — optional code loads for every visitor during block initialization
import { openAdvancedPicker } from './advanced-picker.js';

export default function decorate(block) {
  const trigger = block.querySelector('button');

  trigger?.addEventListener('click', () => {
    openAdvancedPicker(block);
  });
}
```

**Why this is bad:** `advanced-picker.js` is included in the initial code path for every page containing the block, including visitors who never use the optional feature. This increases the block's initial JavaScript cost.

```javascript
// Good — optional code loads after likely interaction intent
export default function decorate(block) {
  const trigger = block.querySelector('button');
  if (!trigger) return;

  let featureModule;

  const loadFeature = () => {
    featureModule ??= import('./advanced-picker.js');
    return featureModule;
  };

  trigger.addEventListener(
    'pointerenter',
    () => {
      void loadFeature();
    },
    { once: true },
  );

  trigger.addEventListener('click', async () => {
    const { openAdvancedPicker } = await loadFeature();
    openAdvancedPicker(block);
  });
}
```

Keep the block's initial UI and trigger lightweight and usable before the import resolves. Use intent-based loading only for optional functionality.

> **Source PRs** — **approach:** nader-eloshaiker/screen-geometry-app#508, ant-design/x#1402, woowacourse/perf-basecamp#163, woowacourse/perf-basecamp#154, elastic/kibana#218442 · **anti-pattern:** n8n-io/n8n#25649, getsentry/gib-potato#275, elastic/kibana#136328, shrinker03/NamasteReactBootcamp#7