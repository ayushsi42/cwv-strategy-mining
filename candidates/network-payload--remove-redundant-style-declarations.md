---
issue_type: network-payload--remove-redundant-style-declarations
parent_strategy: network-payload
risk_tier: low
cwv_metrics: [bundle_size_delta_pct]
source_prs: [adobe/react-spectrum#9090, ant-design/ant-design#56823, ant-design/ant-design#56924]
required_validation:
  - style_macro_used_for_component_styles
  - redundant_style_declarations_removed_or_collapsed
forbidden_techniques: []
---

# Remove redundant style declarations

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metric:** bundle_size_delta_pct

## What this addresses

This strategy reduces CSS bytes by moving style expansion to build time and removing repeated declarations that would otherwise be shipped and parsed by the browser.

The supplied evidence supports two related mechanisms:

1. **Build-time style generation** via a `style` macro that returns class names and generates atomic CSS.
2. **Removal or collapse of redundant declarations** so the emitted stylesheet contains fewer duplicate rules or less duplicated styling work.

The measured outcome in the supplied evidence is **bundle size reduction**.

## Apply / skip gates

### Apply when

- Styles are authored through a build-time style macro or equivalent build-time CSS generator.
- Multiple component states or variants repeat the same declarations and can be expressed once in shared atomic rules.
- A stylesheet or generated style layer contains redundant declarations that can be removed without changing intended behavior.
- The change is limited to style emission, style ordering, or documentation around the supported style macro.

### Skip when

- Styles are runtime-generated in a way that is not supported by the evidence.
- The change requires inventing new CSS optimization behavior not shown in the supplied patches.
- The style duplication is intentional for cascade or override semantics and removing it would alter behavior.
- The code path is not using the supported build-time macro or atomic generation mechanism.

## Required validation

### `style_macro_used_for_component_styles`

**What to validate**

Confirm that component styling is authored through the supported build-time `style` macro mechanism.

**Why this matters**

The evidence shows that the macro is a build-time CSS generator, so this strategy only applies when styles are emitted through that path.

**Evidence-derived checks**

- A `style(...)` call is used to produce a class name for component styling.
- The macro is described as a build-time CSS generator.
- Styling is expressed as property/value objects, including conditional values where applicable.

**Observed evidence**

- `packages/dev/s2-docs/pages/s2/styling.mdx` states that the `style` macro runs at build time and returns a class name.
- `packages/dev/s2-docs/pages/react-aria/styling.mdx` adds a concrete example using `style({ backgroundColor: { default, isHovered, isSelected } })`.

### `redundant_style_declarations_removed_or_collapsed`

**What to validate**

Confirm that the emitted style output no longer contains avoidable duplicate declarations, or that repeated declarations are collapsed into shared atomic rules.

**Why this matters**

The evidence supports reducing shipped CSS by removing repeated declarations or consolidating style generation, not by changing unrelated runtime behavior.

**Evidence-derived checks**

- A patch removes a redundant style declaration.
- A patch reorders or consolidates style generation in a way that reduces duplicated emitted CSS.
- Documentation explicitly warns that atomic CSS can create duplicate rules if not optimized.

**Observed evidence**

- `adobe/react-spectrum#9090` adds documentation warning that atomic CSS can produce a large number of duplicate rules.
- `ant-design/ant-design#56924` removes and repositions a repeated `&-active` block in the select dropdown style generator.
- `ant-design/ant-design#56823` removes global animation/transition declarations from a stylesheet, reducing shipped CSS.

## Recommended approaches

Use the build-time macro to express styles as structured property/value objects, and keep repeated state styling inside the generator rather than duplicating declarations across handwritten CSS.

### Good

```tsx
import {Checkbox} from 'react-aria-components';
import {style} from '@react-spectrum/s2/style' with {type: 'macro'};

<Checkbox
  className={style({
    backgroundColor: {
      default: 'gray-100',
      isHovered: 'gray-200',
      isSelected: 'gray-900'
    }
  })}
/>
```

**Why this is good**

The evidence supports this pattern because the macro is documented as a build-time CSS generator and the example uses conditional values in a single style object.

### Good

```ts
// generalized from the select style patch
const genSingleStyle = (token) => ({
  '&-selected:not(.option-disabled)': {
    color: token.optionSelectedColor,
    fontWeight: token.optionSelectedFontWeight,
  },

  '&-active:not(.option-disabled)': {
    backgroundColor: token.optionActiveBg,
  },
});
```

**Why this is good**

This reflects the supported mechanism: keep state rules explicit, but avoid duplicate placement of the same declaration in the same generator.

## Anti-patterns

The evidence is sufficient to reject shipping redundant global style declarations when they can be removed or localized.

### Bad

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none;
    transition: none;
  }
}
```

**Why this is bad**

In the supplied evidence, this global rule is removed from the stylesheet to reduce shipped CSS. The patch indicates that broad motion declarations are not necessary in the default stylesheet for this strategy.

## How to verify

Measure **bundle_size_delta_pct** before and after the change.

Use the supplied evidence as the verification model:

1. Confirm the style macro or style generator still produces the intended classes.
2. Confirm the emitted CSS or bundle no longer contains the removed redundant declarations.
3. Compare bundle size before and after.

The evidence supports reduction, but does not justify promising a fixed percentage improvement.

## Evidence and confidence

### Observed facts

- `adobe/react-spectrum#9090` documents the `style` macro as a build-time CSS generator and adds guidance that atomic CSS can create duplicate rules if not optimized.
- `ant-design/ant-design#56924` removes a duplicated `&-active` style block from a select dropdown style generator.
- `ant-design/ant-design#56823` removes a global reduced-motion animation/transition rule from a stylesheet.
- The supplied summary reports **3 observations across 2 repositories**, **100% directional consistency**, and a **median absolute measured delta of 66.155** for `bundle_size_delta_pct`.

### Inference

- Reducing redundant style declarations is a valid network-payload optimization when the style system emits CSS at build time.
- The mechanism is most defensible when the change is limited to style generation or stylesheet cleanup, not runtime behavior changes.

## Risks and limitations

- Removing a declaration can change cascade or state behavior if the duplication was intentional.
- Atomic CSS generation can itself create duplicate rules if the input model is not normalized; the evidence warns about this, but does not define a universal fix.
- The supplied evidence supports bundle-size improvement, not a guaranteed user-visible CWV gain.
- Do not generalize this strategy to unrelated markup, script, or runtime optimization techniques.