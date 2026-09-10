---
issue_type: oversized-module-imports
risk_tier: medium
required_validation:
- imported_symbols_usage_traced
- dependency_export_map_verified
- module_side_effects_preserved
- bundle_artifact_compared
forbidden_techniques: []
applicable_flavors:
- eds
- cs
- ams
- headless
source_prs:
- storybookjs/storybook#32594
- Sage-Bionetworks/synapse-web-monorepo#178
- shoelace-style/shoelace#1485
- novuhq/novu#7223
- lambda-curry/forms#30
---
# Oversized module imports

> **Risk tier:** medium

## What this addresses

Barrel imports and aggregate package entrypoints can interfere with tree-shaking or retain code that is not needed by the consuming module. Replacing them with supported, precise entrypoints can reduce delivered JavaScript when the package structure and bundler support it.

## When to apply / when to skip
**Apply when:**
- A bundle analysis identifies a barrel module, namespace import, or package root entrypoint as retaining unused code
- The consuming code uses a small, statically known set of exports
- The dependency publishes documented direct entrypoints through its `exports` map, or the local module structure has stable direct files
- The generated browser bundle can be compared before and after the change

**Skip when:**
- The package does not document the proposed deep import path
- Bundle output shows that the existing import is already fully tree-shaken with no retained unused modules

## Recommended approaches

### Import a specific local module instead of a barrel

Use direct file imports for the helper or feature the consuming module actually needs.

```javascript
// Good: product-card.js
export default async function decorate(block) {
  const { formatPrice } = await import('./utils/format-price.js');
  const { createOptimizedPicture } = await import('../../scripts/aem.js');

  const price = block.querySelector('[data-price]');
  if (price) price.textContent = formatPrice(price.textContent);

  const image = block.querySelector('picture');
  if (!image) {
    block.prepend(createOptimizedPicture('/media/product-placeholder.png', 'Product'));
  }
}
```

A direct file import can produce a narrower dependency graph than importing a utility barrel that re-exports unrelated helpers.

### Use supported package entrypoints

Prefer documented package subpaths or focused packages when a dependency's root entrypoint does not tree-shake effectively.

```javascript
// Good: load only the component modules used by this block
export default async function decorate(block) {
  const [{ decorateDialog }, { decorateModal }] = await Promise.all([
    import('./components/dialog.js'),
    import('./components/modal.js'),
  ]);

  decorateDialog(block.querySelector('.product-dialog'));
  decorateModal(block.querySelector('.product-modal'));
}
```

This approach was used in Storybook to avoid importing from aggregate React Aria entrypoints where dead code was not being removed effectively.

### Preserve required side effects explicitly

When a library requires initialization, keep that initialization as an explicit import and import the feature from its supported direct entrypoint.

```javascript
// Good: explicit registration plus the one feature used by this block
export default async function decorate(block) {
  await import('./register-product-elements.js');
  const { mountProductGallery } = await import('./gallery/mount-product-gallery.js');

  mountProductGallery(block);
}
```

## Anti-patterns

### Namespace import from a local barrel

```javascript
// Bad: product-card.js
export default async function decorate(block) {
  const ProductComponents = await import('./components/index.js');

  ProductComponents.decorateGallery(block);
}
```

**Why this is bad:** Importing an aggregate object can interfere with tree-shaking. In one reported case, importing a shared object was avoided because it caused additional files to be included.

### Broad package-root imports where focused entrypoints are available

```javascript
// Bad: loads an aggregate local component entrypoint
export default async function decorate(block) {
  const { decorateAlert, decorateIcon } = await import('./components/index.js');

  decorateAlert(block.querySelector('.product-alert'));
  decorateIcon(block.querySelector('.product-icon'));
}
```

```javascript
// Better: load documented component entrypoints
export default async function decorate(block) {
  const [{ decorateAlert }, { decorateIcon }] = await Promise.all([
    import('./components/alert.js'),
    import('./components/icon.js'),
  ]);

  decorateAlert(block.querySelector('.product-alert'));
  decorateIcon(block.querySelector('.product-icon'));
}
```

**Why this is bad:** Shoelace changed its React guidance to recommend cherry-picking components because tree-shaking extra components from a single entrypoint proved challenging.

### Deep-importing an undocumented internal file

```javascript
// Bad: assumes an internal module layout is public and stable
export default async function decorate(block) {
  const { createFocusTrap } = await import('./accessibility/internal/focus-trap.js');

  createFocusTrap(block.querySelector('.cmp-product-card__dialog'));
}
```

**Why this is bad:** Use documented package entrypoints where available so that imports follow the package's supported export structure.