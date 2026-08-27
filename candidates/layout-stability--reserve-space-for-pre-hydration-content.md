---
issue_type: layout-stability--reserve-space-for-pre-hydration-content
parent_strategy: layout-stability
risk_tier: low
cwv_metrics: [CLS]
source_prs:
  - harbor-framework/terminal-bench-3#183
  - internetarchive/openlibrary#11812
  - pulumi/docs#18139
required_validation:
  - pre_hydration_slot_or_widget_is_hidden_until_upgrade
  - replacement_content_has_reserved_space_before_hydration
forbidden_techniques: []
---

# Reserve space for pre-hydration content

> **Risk tier:** low · **Parent strategy:** layout-stability · **CWV metric:** CLS

## What this addresses

Use this strategy when content appears before hydration or upgrade, then changes shape, visibility, or replacement behavior once client-side code initializes.

The evidence supports two distinct but related layout-stability actions:

1. hide only the unstable pre-hydration fragment so the stable fallback remains visible
2. reserve the final occupied space so hydration does not push surrounding content

This is a CLS mitigation pattern for pre-hydration or upgrade-time changes, not a general loading-state pattern.

## When to apply / when to skip

### Apply when
- a custom element, widget, or injected control changes its footprint after hydration or upgrade
- the pre-hydration state would otherwise show transient content that later gets replaced
- the final collapsed or default height is known and can be reserved explicitly
- you can hide only the unstable fragment without removing the whole container from layout

### Skip when
- the element already has the same footprint before and after hydration
- the final occupied size is unknown and cannot be reserved defensibly
- the only available fix would be to guess a height with no evidence from the component’s default rendering
- the issue is not pre-hydration or upgrade-related

## Required validation

### `pre_hydration_slot_or_widget_is_hidden_until_upgrade`

**What this validates:**  
The unstable subcontent is suppressed before hydration or replacement, while the surrounding container remains in the document flow.

**Evidence from the patches:**
- `pulumi-user-toggle:not(.hydrated) [slot="signed-in"] { display: none; }`
- `.github-widget > a.github-button { visibility: hidden; }`

**How to verify:**
- Before hydration, inspect the page and confirm the unstable fragment is not visible.
- Confirm the outer container still occupies its normal place in layout.
- After hydration or replacement, confirm the stable interactive content appears without shifting the surrounding page.

### `replacement_content_has_reserved_space_before_hydration`

**What this validates:**  
The host or container has explicit reserved space before the component becomes interactive.

**Evidence from the patches:**
- `<ol-read-more ... style="min-height: 141px">`
- `ol-read-more { min-height: 121px; visibility: hidden; overflow: hidden; }`
- `ol-read-more[label-size="small"] { min-height: 107px; }`
- `this.maxHeight = '80px';` in the component default
- the component later clears temporary styles after render

**How to verify:**
- Inspect the pre-hydration DOM and confirm the host has a reserved height or min-height.
- Confirm the reserved size matches the component’s expected collapsed/default footprint.
- Confirm the component becomes visible and interactive without changing the surrounding layout footprint.

## Evidence-backed implementation shapes

### 1) Hide only the unstable fragment until upgrade

This is supported by the Pulumi header patch.

```scss
pulumi-user-toggle:not(.hydrated) [slot="signed-in"] {
  display: none;
}

.github-widget > a.github-button {
  visibility: hidden;
}
```

**Why this fits the evidence:**  
The unstable part is suppressed, but the surrounding header structure remains in place.

### 2) Reserve the host’s space with an explicit height

This is supported by the OpenLibrary `ol-read-more` changes.

```html
<ol-read-more
  max-height="100px"
  style="min-height: 141px"
  more-text="Read more"
  less-text="Read less"
>
  <p>Long content here...</p>
</ol-read-more>
```

**Why this fits the evidence:**  
The component uses a known collapsed/default height and reserves space before it becomes interactive.

### 3) Set page-level reserved space for the custom element before definition

This is also supported by the OpenLibrary patch.

```html
<style>
  ol-read-more {
    min-height: 121px;
    visibility: hidden;
    overflow: hidden;
  }

  ol-read-more[label-size="small"] {
    min-height: 107px;
  }
</style>
```

**Why this fits the evidence:**  
The host is hidden before definition, but the reserved height prevents layout collapse or expansion when the component appears.

## Good examples

### Good: hide only the unstable slot
```scss
pulumi-user-toggle:not(.hydrated) [slot="signed-in"] {
  display: none;
}
```

### Good: hide a replacement anchor before external widget takeover
```scss
.github-widget > a.github-button {
  visibility: hidden;
}
```

### Good: reserve explicit space on the host
```html
<ol-read-more max-height="100px" style="min-height: 141px">
  <p>Long content here...</p>
</ol-read-more>
```

### Good: reserve default space before definition
```html
<style>
  ol-read-more {
    min-height: 121px;
    visibility: hidden;
    overflow: hidden;
  }

  ol-read-more[label-size="small"] {
    min-height: 107px;
  }
</style>
```

## Bad examples

### Bad: hide the whole region instead of only the unstable fragment
```scss
.header-container {
  display: none;
}
```

**Why this is bad:**  
This removes the entire region from layout rather than preserving the stable container and reserving space.

### Bad: omit reserved space for a component that changes footprint
```html
<ol-read-more more-text="Read More" less-text="Read Less">
  <p>Long content here...</p>
</ol-read-more>
```

**Why this is bad:**  
The evidence shows that the component should have a known default footprint or explicit reserved height before hydration.

## How to verify

Use CLS-focused before/after measurement on the affected page or interaction.

Verify that:
- the pre-hydration state no longer causes visible movement when the widget upgrades
- the reserved-space host keeps surrounding content from shifting when the component initializes
- the measured CLS signal is compared before and after the change

For a component like `ol-read-more`, confirm both:
- the host has the expected reserved height before definition
- the component becomes visible and interactive without changing the surrounding layout footprint

## Evidence and confidence

### Observed facts
- Pulumi docs changed header markup and CSS to suppress unstable pre-hydration content and keep the top nav positioning consistent.
- OpenLibrary changed `ol-read-more` from line-based truncation to height-based truncation with explicit reserved space.
- OpenLibrary also added page-level CSS to hide `ol-read-more` before definition and set default min-heights for the host.
- The only measured metric supplied is CLS.
- No regression PR evidence was supplied.

### Inference
- Reserving space and hiding only the unstable fragment are the mechanisms most directly supported by the patches for reducing CLS in pre-hydration scenarios.
- This strategy is best treated as a low-risk layout-stability fix when the final footprint is known or can be derived from the component’s default rendering.

### Source PRs
- `pulumi/docs#18139`
- `internetarchive/openlibrary#11812`

## Risks and limitations

- This strategy depends on knowing the stable footprint of the hydrated content; if the final size is uncertain, the reservation can be wrong and still shift layout.
- Hiding content too broadly can create blank areas or accessibility issues if the fallback is not preserved.
- The evidence supports height reservation and targeted hiding, not generic removal of all pre-hydration content.
- The patches do not establish browser support boundaries, universal sizing formulas, or a guaranteed CLS delta.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: layout-stability--reserve-space-for-pre-hydration-content`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
