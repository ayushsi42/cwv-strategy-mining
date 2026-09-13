### Remove duplicate CSS-in-JS style registration

When a component already has a shared style generator, register the style once in the shared path instead of creating a separate hook or per-component style block for the same rules.

```js
// Good: shared style generator used by the style system
export function decorate(block) {
  const icon = block.querySelector('.icon');
  if (!icon) return;

  icon.classList.add('icon--styled');
}
```

```css
/* Good: the reusable style object lives in one place */
.icon--styled {
  display: block;
}
```

**Bad example:**

```js
// Bad: the same rules are registered again in a component-specific hook
export function decorate(block) {
  const icon = block.querySelector('.icon');
  if (!icon) return;

  icon.classList.add('icon--styled');
  icon.classList.add('icon-button--styled');
}
```

**Why this is bad:**
- The same selector set is emitted more than once.
- It can increase style registration work at runtime.
- It makes future changes harder because the shared rules now have multiple call sites.
- Duplicate style generation can lead to larger CSS output and inconsistent overrides.

This keeps the style output centralized, avoids repeated registration work, and reduces the chance of emitting duplicate CSS for the same selector set.

> **Source PRs** — **approach:** Bharadwaj07/code-rank#1, medic/cht-core#7257, discourse/discourse#28680, OCA/website#853, Strongminds/kitos_frontend#4 · **anti-pattern:** ant-design/ant-design#53954, ant-design/ant-design#51897, adobecom/express-milo#634