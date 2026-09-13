### Delay unit-value parsing until typing pauses

Use this as a reviewer-guided fix for unit inputs where parsing while typing modifies input values, particularly for invalid or formatted intermediate values such as `096`.

**Anti-pattern: Parse and reformat on every keystroke**

```javascript
// EDS: blocks/unit-input/unit-input.js
export default function decorate(block) {
  const input = block.querySelector('input[data-unit-input]');

  input.addEventListener('input', ({ target }) => {
    const parsedValue = parseUnitValue(target.value);
    updateUnitSummary(block, parsedValue);
  });
}

// CS/AMS: /apps/example/clientlibs/clientlib-unit-input/js/unit-input.js
(() => {
  document.querySelectorAll('[data-unit-input-block]').forEach((block) => {
    const input = block.querySelector('input[data-unit-input]');
    if (!input) return;

    input.addEventListener('input', ({ target }) => {
      const parsedValue = parseUnitValue(target.value);
      updateUnitSummary(block, parsedValue);
    });
  });
})();
```

**Why this is bad:** Parsing runs for every keystroke, including invalid or formatted intermediate values. Parsing while typing can modify the input value before the user has finished entering it.

**Approach: Debounce parsing until typing pauses**

```javascript
// EDS: blocks/unit-input/unit-input.js
export default function decorate(block) {
  const input = block.querySelector('input[data-unit-input]');
  if (!input) return;

  let debounceTimer;

  input.addEventListener('input', ({ target }) => {
    const rawValue = target.value;

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const parsedValue = parseUnitValue(rawValue);
      updateUnitSummary(block, parsedValue);
    }, 500);
  });
}

// CS/AMS: /apps/example/clientlibs/clientlib-unit-input/js/unit-input.js
(() => {
  document.querySelectorAll('[data-unit-input-block]').forEach((block) => {
    const input = block.querySelector('input[data-unit-input]');
    if (!input) return;

    let debounceTimer;

    input.addEventListener('input', ({ target }) => {
      const rawValue = target.value;

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const parsedValue = parseUnitValue(rawValue);
        updateUnitSummary(block, parsedValue);
      }, 500);
    });
  });
})();
```

> **Source PRs** — **approach:** rancher/dashboard#5670