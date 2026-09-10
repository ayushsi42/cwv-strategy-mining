---
issue_type: overlay-clipping
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: high
required_validation:
- Reproduce the clipping on the affected viewport, zoom level, and writing direction.
- Confirm that the attributed INP interaction opens, closes, or selects from the affected
  overlay.
- Inventory existing overlay primitives before introducing new positioning behavior.
- Verify keyboard dismissal, focus restoration, outside-click behavior, and touch
  interaction.
- Measure the overlay code delivered to the affected page or application surface.
- Identify the block, component clientlib, or host application that owns the overlay.
forbidden_techniques:
- pattern: '@floating-ui/(?:dom|react|react-dom)\b'
  reason: Avoid adding a general-purpose floating-positioning dependency without a
    documented need. One reviewed change noted that Floating UI would add approximately
    7 KB of bundle size.
- pattern: \b(?:FloatingLayer|useFloatingLayer)\b
  reason: Avoid generic overlay abstractions when a narrowly scoped component can
    serve the use case. A reviewed change raised concerns that broad wrappers add
    concepts and may reduce tree-shaking effectiveness.
- pattern: console\.log\s*\(
  reason: Do not leave debug logging in component code.
flavor_overrides:
  eds:
    extra_validation:
    - Trace the block markup and decorate lifecycle before changing overlay behavior.
  cs:
    extra_validation:
    - Confirm the component clientlib category and HTL output path.
  ams:
    extra_validation:
    - Confirm the component clientlib category and whether the rendered output originates
      in JSP, HTL, or an include chain.
  headless:
    extra_validation:
    - Confirm that the consuming application owns the overlay primitive and its focus-management
      contract.
source_prs:
- razorpay/blade#1284
- novuhq/novu#5828
- utrad-ical/circus#407
- sumup-oss/circuit-ui#3112
---
# Overlay clipping

> **Risk tier:** high · **Applies to:** EDS, CS, AMS, Headless

## What this addresses

A dropdown or popover can be clipped or overflow at a viewport edge or within an overflow container. Changes to overlay positioning, focus management, dismissal behavior, or delivered JavaScript require manual review.

## When to apply / when to skip
**Apply when:**

- INP attribution identifies opening, closing, or selecting an item in a dropdown, popover, date picker, or navigation menu as the delayed interaction.
- The overlay is visibly clipped or overflows at the affected viewport, zoom level, or writing direction.
- The site or host application already has a reviewed overlay or popover primitive whose focus, keyboard, and dismissal behavior is understood.
- The affected component and its clientlib, block lifecycle, or host-application ownership are clearly scoped.

**Skip when:**

- The interaction is not the attributed INP culprit, even if the overlay has a visual positioning defect.
- The overlay contains a form, calendar, or dialog whose focus-trapping and return-focus contract has not been tested.
- The component is used across multiple templates or applications and its existing overlay implementations have not been inventoried.

## Recommended approaches

### Reuse an existing overlay primitive where it meets the requirements

Prefer an existing, reviewed popover or overlay primitive over a new generic abstraction when it can meet the component's requirements.

Circuit UI refactored `DateInput` from `Dialog` to `Popover`. Its PR describes the change as making the codebase more coherent and reusing Popover state-management, accessibility, and styling behavior. The same PR also improved floating-element positioning.

Verify the component's keyboard behavior, focus restoration, dismissal behavior, touch interaction, and delivered JavaScript before adoption.

### Scope overlay behavior to the owning component

Keep overlay behavior scoped to the component or application surface that owns the overlay, and verify the relevant clientlib, block lifecycle, or host-application boundary before changing markup or positioning behavior.

### Use a narrowly scoped component where possible

A reviewed main-navigation change rejected a generic `FloatingLayer` abstraction in favor of a wrapper focused on top-level navigation menus. Where the use case is similarly narrow, prefer a component-specific implementation over a reusable abstraction that bundles hover, click, focus, middleware, and animation behavior for unrelated overlays.

## Anti-patterns

### Adding a general-purpose floating-positioning dependency without assessing bundle impact

```javascript
// EDS: blocks/navigation/navigation.js
// Avoid loading a vendored general-purpose positioning library without
// measuring its delivered size for this block.
export default async function decorate(block) {
  const { positionOverlay } = await import('./vendor/position-overlay.js');

  const trigger = block.querySelector('button');
  const panel = block.querySelector('[role="menu"]');

  trigger.addEventListener('click', () => {
    positionOverlay(trigger, panel);
  });
}

// Headless host application: src/navigation/overlay.js
// Avoid adding an unreviewed generic positioning module to the host bundle.
export async function openNavigationOverlay(trigger, panel) {
  const { positionOverlay } = await import('./vendor/position-overlay.js');
  positionOverlay(trigger, panel);
}
```

```xml
<!-- CS/AMS: ui.apps/src/main/content/jcr_root/apps/example/components/navigation/clientlibs/site/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.navigation]"
    dependencies="[vendor.generic-positioning]"/>
```

```javascript
// CS/AMS: clientlibs/site/js/navigation.js
// Avoid adding the generic positioning clientlib category unless its delivered
// cost and the component-specific alternative have been reviewed.
(function (document) {
  const trigger = document.querySelector('.cmp-navigation__trigger');
  const panel = document.querySelector('.cmp-navigation__panel');

  if (!trigger || !panel) return;

  trigger.addEventListener('click', () => {
    window.GenericPositioning.position(trigger, panel);
  });
}(document));
```

A Novu review noted that Floating UI would add approximately 7 KB of bundle size in that context. A Razorpay dropdown-positioning change that introduced Floating UI also increased configured bundle-size limits.

### Creating a generic floating abstraction that every component imports

```javascript
// EDS: blocks/navigation/navigation.js
// Avoid importing a shared controller that attempts to own every overlay type.
export default async function decorate(block) {
  const { OverlayController } = await import('./overlay-controller.js');

  const controller = new OverlayController(
    block.querySelector('button'),
    block.querySelector('[role="menu"]'),
  );

  controller.open();
}
```

```javascript
// EDS: blocks/navigation/overlay-controller.js
// This broad controller mixes behavior for unrelated overlay components.
export class OverlayController {
  constructor(reference, overlay, options = {}) {
    this.reference = reference;
    this.overlay = overlay;
    this.options = options;
  }

  open() {
    // Generic hover, click, focus, positioning, and animation behavior.
  }
}
```

```xml
<!-- CS/AMS: ui.apps/src/main/content/jcr_root/apps/example/components/navigation/clientlibs/site/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.navigation]"/>
```

```javascript
// CS/AMS: clientlibs/site/js/overlay-controller.js
// Avoid making this clientlib controller the dependency of every component.
(function (window) {
  class OverlayController {
    constructor(reference, overlay, options = {}) {
      this.reference = reference;
      this.overlay = overlay;
      this.options = options;
    }

    open() {
      // Generic hover, click, focus, positioning, and animation behavior.
    }
  }

  window.ExampleOverlayController = OverlayController;
}(window));
```

```javascript
// Headless host application: src/overlay-controller.js
// Avoid making this generic controller the default import for all overlays.
export class OverlayController {
  constructor(reference, overlay, options = {}) {
    this.reference = reference;
    this.overlay = overlay;
    this.options = options;
  }

  open() {
    // Generic hover, click, focus, positioning, and animation behavior.
  }
}
```

A review of a navigation-menu implementation raised concerns that a generic wrapper could add concepts to learn and may make tree shaking less effective. The requested alternative was a simpler wrapper focused on top-level navigation menus.

### Relying on fixed directional positioning without reproducing overflow cases

```css
/* Validate this positioning against the affected viewport. */
.cmp-dropdown__panel {
  position: absolute;
  right: 0;
  bottom: 20px;
  min-width: 240px;
  max-width: 400px;
}
```

A Razorpay dropdown issue reproduced an overlay overflowing the screen width and was addressed with positioning changes.

### Leaving debug logging in component code

```javascript
// EDS: blocks/navigation/navigation.js
// Avoid leaving temporary debug output in the delivered block.
export default async function decorate(block) {
  const { markOverlayDebugState } = await import('./debug-overlay.js');

  const panel = block.querySelector('[role="menu"]');
  markOverlayDebugState(panel, 'opened');
}
```

```javascript
// EDS: blocks/navigation/debug-overlay.js
// Temporary debug instrumentation must be removed before delivery.
export function markOverlayDebugState(panel, state) {
  panel.dataset.debugOverlayState = state;
}
```

```xml
<!-- CS/AMS: ui.apps/src/main/content/jcr_root/apps/example/components/navigation/clientlibs/site/.content.xml -->
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[example.navigation]"/>
```

```javascript
// CS/AMS: clientlibs/site/js/navigation-debug.js
// Temporary debug instrumentation must not remain in the component clientlib.
(function (document) {
  const panel = document.querySelector('.cmp-navigation__panel');

  if (panel) {
    panel.dataset.debugOverlayState = 'opened';
  }
}(document));
```

```javascript
// Headless host application: src/navigation/debug-overlay.js
// Temporary debug instrumentation must not remain in the delivered application.
export function markOverlayDebugState(panel, state) {
  panel.dataset.debugOverlayState = state;
}
```

## Flavor-specific notes

### EDS

Trace the owning block's markup and decorate lifecycle before changing overlay behavior. For below-the-fold enhancements, validate loading behavior and keyboard and touch interaction after the enhancement is available.

### CS

Trace the HTL component, its template use, and the clientlib category before recommending consolidation. Verify focus and dismissal requirements for each affected template.

### AMS

Verify whether the rendered overlay originates in JSP, HTL, or a nested `<cq:include>` chain before changing a clientlib or markup contract.

### Headless

Apply changes in the consuming application that owns the overlay. Confirm ownership of focus restoration, Escape dismissal, touch behavior, and route-change cleanup before consolidating popover behavior.