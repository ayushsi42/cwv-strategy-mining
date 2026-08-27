---
issue_type: tooltip-interaction-lag
applicable_flavors: [eds, cs, ams, headless]
risk_tier: medium

required_validation:
  - tooltip_is_hover_or_focus_driven
  - tooltip_state_updates_are_localized
  - no_existing_delay_group_or_debounce_logic
  - tooltip_close_open_timing_is_testable

forbidden_techniques:
  - pattern: '\bsetTimeout\s*\(\s*[^,]+,\s*(?!0\b)\d{3,}\s*\)'
    reason: "Don't add long fixed hover delays without a clear cancellation path — they can make pointer interactions feel sluggish and can worsen INP"
  - pattern: '\bdebounce\s*\('
    reason: "Don't debounce tooltip hover state updates by default — it can create stale hover state and delayed feedback"
  - pattern: '\bthrottle\s*\('
    reason: "Don't throttle tooltip hover state updates — it can leave the active tooltip behind the pointer and feel unresponsive"
  - pattern: 'delay(Group|Ref|Ms|Time)?\s*[:=]\s*[^;\n]*\b(2\d{2,}|[3-9]\d{2,})\b'
    reason: "Don't introduce large shared delay-group values — stale timing state is the regression class this playbook is meant to avoid"

# Tooltip interaction lag

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** INP

## What this addresses

Tooltips that update active state on every rapid pointer move, or that keep stale delay-group timing after a tooltip unmounts, can make hover interactions feel sticky and slow. The goal is to keep tooltip feedback immediate while preventing outdated hover timers or shared delay state from piling up and delaying the next interaction.

## When to apply

**Apply when:**
- Tooltip open/close state is driven by hover, focus, or pointer-enter/leave events
- Rapid pointer movement can enqueue repeated tooltip updates
- A shared delay group, provider, or context can outlive the active tooltip and retain stale timing state
- The tooltip content is localized and can be updated without redesigning the whole interaction model

**Skip when:**
- The issue is not tooltip-related, but a broader menu, popover, or dialog timing problem
- The tooltip is already instant and the lag comes from layout, paint, or network work elsewhere
- The interaction is intentionally delayed for accessibility or product reasons and the delay is already validated
- The tooltip is self-managed by a third-party library with no safe local timing/state hook to adjust

## Recommended approaches

### Keep hover updates immediate, but cancel stale pending work

Use a cancelable timer or cleanup path so only the latest hover intent wins. The key is to avoid a buildup of queued tooltip activations when the pointer moves quickly across many targets.

```js
// Good: cancel stale hover work and keep the latest pointer intent
let openTimer = null;
let closeTimer = null;

function handleMouseEnter(label) {
  clearTimeout(closeTimer);
  clearTimeout(openTimer);

  openTimer = setTimeout(() => {
    setActiveTooltip(label);
  }, 0);
}

function handleMouseLeave() {
  clearTimeout(openTimer);
  closeTimer = setTimeout(() => {
    setActiveTooltip(null);
  }, 0);
}
```

This keeps the interaction responsive while preventing older hover events from firing after the pointer has already moved on.

### Reset shared delay-group state when the active tooltip changes or unmounts

If tooltips share a provider/context for open and close timing, make sure inactive consumers do not clear the active context and that updated timing props are reflected immediately.

```tsx
// Good: keep the active delay context current and preserve it across inactive unmounts
function FloatingDelayGroup({ delay, children }) {
  const delayRef = React.useRef(delay);
  const initialDelayRef = React.useRef(delay);
  const currentIdRef = React.useRef<string | null>(null);

  React.useLayoutEffect(() => {
    initialDelayRef.current = delay;

    if (!currentIdRef.current) {
      delayRef.current = delay;
      return;
    }

    delayRef.current = {
      open: delayRef.current.open,
      close: delay.close,
    };
  }, [delay]);

  return children;
}
```

This pattern avoids stale close timing and prevents an inactive tooltip from wiping out the active group state.

### Keep tooltip content updates local to the hovered item

When the tooltip content depends on the hovered row or legend entry, update only the active item instead of re-rendering a large shared list on every pointer event.

```svelte
<!-- Good: localized tooltip content -->
<script lang="ts">
  let { title, shortcut } = $props();
</script>

<button
  on:pointerenter={() => setHoveredTitle(title)}
  on:pointerleave={() => setHoveredTitle(null)}
>
  {title}
</button>

{#if hoveredTitle === title}
  <div role="tooltip">
    {title}
  </div>
{/if}
```

This reduces unnecessary work during hover and keeps the pointer interaction snappy.

## Anti-patterns

### Debouncing the active tooltip update without cancellation discipline

```js
// Bad
import debounce from 'lodash.debounce';

const debouncedHandleMouseEnter = debounce(() => {
  setActiveTraceLabel(label);
}, 700);

function handleOnMouseEnter() {
  debouncedHandleMouseEnter();
}
```

**Why this is bad:** A debounced hover update can delay feedback and may leave stale tooltip state queued behind fast pointer movement.

### Letting inactive tooltip unmounts clear the active delay context

```tsx
// Bad
useEffect(() => {
  return () => {
    currentContextRef.current = null;
    delayRef.current = initialDelayRef.current;
  };
}, []);
```

**Why this is bad:** Clearing shared delay state from an inactive consumer can break the next tooltip transition and create inconsistent hover timing.

### Adding a fixed hover delay to every tooltip interaction

```js
// Bad
function handleMouseEnter() {
  setTimeout(() => {
    setTooltipOpen(true);
  }, 700);
}
```

**Why this is bad:** A blanket delay can make hover interactions feel sluggish, even when the user is intentionally moving to a tooltip target.

### Recomputing tooltip state for the whole list on every pointer move

```jsx
// Bad
function onMouseMove() {
  setHoveredId(Date.now());
  setAllLegendItems(items.map((item) => ({ ...item, active: item.id === hoveredId })));
}
```

**Why this is bad:** Updating the entire collection on every mouse event can amplify work during rapid pointer movement and hurt INP.

## Flavor-specific notes

### EDS

Prefer block-local state and event handlers in the block's `decorate(block)` path. If the tooltip is rendered inside a block, keep the hover logic inside that block rather than introducing page-global listeners.

```js
export default function decorate(block) {
  const tooltip = block.querySelector('[role="tooltip"]');
  const trigger = block.querySelector('[data-tooltip-trigger]');

  if (!tooltip || !trigger) return;

  let openTimer = null;

  trigger.addEventListener('pointerenter', () => {
    clearTimeout(openTimer);
    openTimer = setTimeout(() => {
      tooltip.hidden = false;
    }, 0);
  });

  trigger.addEventListener('pointerleave', () => {
    clearTimeout(openTimer);
    tooltip.hidden = true;
  });
}
```

### CS

If the tooltip lives in a clientlib-backed component, keep the timing logic in the component JS and avoid pushing hover state into a shared clientlib singleton unless multiple components truly need it. Validate that the updated behavior does not change other templates that reuse the same component. For clientlib delivery, use the standard `.content.xml` clientlib structure rather than package or bundler configuration.

### AMS

If the tooltip is rendered through JSP/HTL plus clientlib JS, keep the timing fix in the client-side behavior layer. Avoid broad server-side markup changes unless the tooltip trigger markup itself must change. For clientlib delivery, use the standard `.content.xml` clientlib structure.

### Headless

Apply the fix only in the client-rendered tooltip component. Do not move the timing logic into the API layer; the problem is interaction state, not data shape.