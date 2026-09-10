applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

### Delay unit-value parsing while typing

For unit-value inputs, delay parsing until after the user pauses typing. The referenced change adds debounced input handling and delays `UnitInput` parsing to avoid modifying input values while they are being entered.

#### Behavior to avoid: parse and validate on every keystroke

```javascript
// blocks/unit-input/unit-input.js (EDS)
export default function decorate(block) {
  const input = block.querySelector('input');
  const output = block.querySelector('[data-unit-output]');

  input.addEventListener('input', () => {
    const parsedValue = parseUnitValue(input.value);
    const validation = validateUnitValue(parsedValue);

    output.textContent = validation.valid
      ? formatUnitValue(parsedValue.value)
      : validation.message;
  });
}

// clientlibs/unit-input/js/unit-input.js (CS/AMS)
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.unit-input').forEach((container) => {
      const input = container.querySelector('input');
      const output = container.querySelector('[data-unit-output]');

      input.addEventListener('input', () => {
        const parsedValue = parseUnitValue(input.value);
        const validation = validateUnitValue(parsedValue);

        output.textContent = validation.valid
          ? formatUnitValue(parsedValue.value)
          : validation.message;
      });
    });
  });
})();
```

**Why avoid this:** parsing and related value handling can run for intermediate values while the user is still typing. For unit inputs, this can modify invalid or formatted intermediate values before entry is complete.

#### Approach: debounce unit-value parsing

```javascript
// blocks/unit-input/unit-input.js (EDS)
export default function decorate(block) {
  const input = block.querySelector('input');
  const output = block.querySelector('[data-unit-output]');
  let parseTimer;

  input.addEventListener('input', () => {
    window.clearTimeout(parseTimer);

    parseTimer = window.setTimeout(() => {
      const parsedValue = parseUnitValue(input.value);

      if (parsedValue.valid) {
        output.textContent = formatUnitValue(parsedValue.value);
      }
    }, 500);
  });
}

// clientlibs/unit-input/js/unit-input.js (CS/AMS)
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.unit-input').forEach((container) => {
      const input = container.querySelector('input');
      const output = container.querySelector('[data-unit-output]');
      let parseTimer;

      input.addEventListener('input', () => {
        window.clearTimeout(parseTimer);

        parseTimer = window.setTimeout(() => {
          const parsedValue = parseUnitValue(input.value);

          if (parsedValue.valid) {
            output.textContent = formatUnitValue(parsedValue.value);
          }
        }, 500);
      });
    });
  });
})();
```

Delay parsing while the user types so intermediate or temporarily invalid values are not rewritten during entry. The referenced `UnitInput` change uses a default delay of 500 ms.

> **Source PRs** — **approach:** rancher/dashboard#5670