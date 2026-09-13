---
issue_type: interaction-latency
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
required_validation:
- interaction_target_identified
- interaction_work_is_dom_bound
- initial_mount_cost_is_material
- no_ssr_dependency_on_hidden_content
forbidden_techniques:
- pattern: (?:^|\\n)\\s*//\\s*Bad\\b
  reason: Matches a known anti-pattern from the source evidence.
- pattern: (?:^|\\n)\\s*display\\s*:\\s*none\\b
  reason: Matches a known anti-pattern from the source evidence.
- pattern: (?:^|\\n)\\s*hidden\\b
  reason: Matches a known anti-pattern from the source evidence.
source_prs:
- arch-linux-gui/web#19
- accidentalgenius09/MassCare#27
- okp4/dataverse-portal#442
- okp4/dataverse-portal#485
- mui/base-ui#1906
---
# Interaction latency

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** INP

## What this addresses

This issue type targets interaction work that mounts or renders a large portal, dropdown, popover, or select list before the user actually opens it. Deferring that DOM work until the control is opened reduces main-thread work during the interaction and can improve INP.

## When to apply / when to skip

**Apply when:**
- A control mounts a large hidden menu, portal, or option list on initial render
- The interaction target is a select, combobox, popover, tooltip, or similar overlay that can stay unmounted until first open
- The expensive work is DOM/rendering work, not data fetching or business logic
- The closed state can be represented with a lightweight placeholder label

**Skip when:**
- The content must exist in the DOM for SSR, SEO, or accessibility before interaction
- The control depends on immediate measurement of hidden items during mount
- The expensive work is not mount-time DOM work, but network fetch, validation, or server round-trip
- The component is already virtualized or otherwise avoids mounting the full list up front
- The interaction is not user-opened overlay UI, but a different INP bottleneck such as event handler churn or layout thrash

## Recommended approaches

### Defer portal mounting until first open

```html
<sly data-sly-use.model="com.example.components.SelectModel">
  <button
    type="button"
    aria-expanded="${model.open}"
    data-select-toggle
  >
    ${model.label}
  </button>

  <sly data-sly-test="${model.mounted}">
    <div role="listbox" data-select-portal>
      <sly data-sly-list.option="${model.options}">
        <div role="option" data-value="${option.value}">
          ${option.label}
        </div>
      </sly>
    </div>
  </sly>
</sly>
```

```js
export default function decorate(block) {
  const toggle = block.querySelector("[data-select-toggle]");
  let mounted = false;

  toggle?.addEventListener("click", () => {
    mounted = true;
    block.dataset.open = "true";

    if (!block.querySelector("[data-select-portal]")) {
      const portal = document.createElement("div");
      portal.setAttribute("role", "listbox");
      portal.setAttribute("data-select-portal", "");
      block.append(portal);
    }
  });
}
```

This keeps the heavy overlay out of the initial render path and only pays the mount cost when the user actually opens the control. After the first open, the portal can remain mounted so subsequent toggles are cheap.

### Keep the closed trigger label lightweight

```html
<sly data-sly-use.model="com.example.components.SelectValueModel">
  <span>${model.label || model.fallback}</span>
</sly>
```

Use a simple initial label for the closed state instead of rendering the full option tree just to derive text content. This preserves the visible trigger text without forcing the list to mount on page load.

### Mount large option lists only when needed

```html
<sly data-sly-use.model="com.example.components.LargeSelectModel">
  <div>
    <button type="button" aria-expanded="${model.open}">
      Choose an item
    </button>

    <sly data-sly-test="${model.open}">
      <ul role="listbox">
        <sly data-sly-list.option="${model.options}">
          <li role="option" data-value="${option.value}">
            ${option.label}
          </li>
        </sly>
      </ul>
    </sly>
  </div>
</sly>
```

This avoids rendering hundreds or thousands of items until the user opens the control, which reduces interaction-time scripting and layout work.

## Anti-patterns

### Mounting the full portal on initial render

```html
<sly data-sly-use.model="com.example.components.SelectMenuModel">
  <div role="listbox" data-select-portal>
    <sly data-sly-list.child="${model.children}">
      ${child}
    </sly>
  </div>
</sly>
```

**Why this is bad:** The portal and all of its children still mount on page load, so the user pays the render cost before any interaction.

### Deriving the trigger label from hidden option DOM

```html
<sly data-sly-use.model="com.example.components.SelectValueModel">
  <span>${model.selectedOptionText}</span>
</sly>
```

```js
export default function decorate(block) {
  const options = Array.from(block.querySelectorAll("[data-value]"));
  const selected = block.dataset.selected;
  const node = options.find((el) => el.dataset.value === selected);
  block.querySelector("[data-select-label]").textContent = node?.textContent || "";
}
```

**Why this is bad:** Reading label text from option DOM forces the option tree to exist at mount time, which recreates the expensive work you were trying to defer.

### Rendering a huge list and hiding it with CSS

```html
<sly data-sly-use.model="com.example.components.LargeSelectModel">
  <ul class="select-list">
    <sly data-sly-list.option="${model.options}">
      <li>${option.label}</li>
    </sly>
  </ul>
</sly>
```

```css
.select-list {
  visibility: hidden;
}
```

**Why this is bad:** Hiding the UI does not avoid the initial render cost of creating every list item.

### Recreating the portal on every toggle

```html
<sly data-sly-use.model="com.example.components.SelectMenuModel">
  <sly data-sly-test="${model.open}">
    <div>
      <sly data-sly-list.child="${model.children}">
        ${child}
      </sly>
    </div>
  </sly>
</sly>
```

**Why this is bad:** Tearing the portal down on close and rebuilding it on every open repeats the mount work instead of amortizing it after the first interaction.

## Flavor-specific notes

### CS

This pattern is most useful for client-rendered overlays in AEM sites, such as custom selects, filters, and popovers in editable templates or SPA-like sections. Keep the closed state SSR-safe: render the trigger label in the HTML, then mount the portal only after the user opens the control.

If the control is part of an AEM component, prefer a small HTL-rendered trigger plus a client-side overlay module rather than server-rendering the full option tree into the page.

### AMS

Use this for client-side widgets layered onto JSP/HTL-rendered pages when the overlay content is large and interaction-driven. Keep the initial markup minimal and avoid server-side rendering of every option if the user only needs the list after clicking the trigger.

If the component is embedded in a broader AEM page, make sure the trigger remains functional without requiring the portal to exist at load time.

### Headless

This is primarily a headless-app pattern: defer mounting large interactive overlays until the user opens them. It is especially relevant for select menus, filter drawers, and popovers that are rendered entirely on the client and can otherwise dominate the interaction frame.