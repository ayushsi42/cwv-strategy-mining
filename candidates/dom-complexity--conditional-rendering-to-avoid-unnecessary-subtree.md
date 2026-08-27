---
issue_type: dom-complexity--conditional-rendering-to-avoid-unnecessary-subtree
parent_strategy: dom-complexity
risk_tier: low
cwv_metrics:
  - Lighthouse DOM size
  - Lighthouse DOM size / TBT
  - Lighthouse DOM size / main-thread work
  - DOM size / main-thread work
source_prs:
  - jeong-sik/masc-mcp#8059
  - skalenetwork/portal#619
  - vivid-planet/comet#4235
required_validation:
  - address_present_for_subtree
  - selected_variant_is_known
  - required_state_is_available
forbidden_techniques: []
---

# Conditional rendering to avoid unnecessary subtree

> **Risk tier:** low · **Parent strategy:** dom-complexity · **CWV metrics:** Lighthouse DOM size, Lighthouse DOM size / TBT, Lighthouse DOM size / main-thread work, DOM size / main-thread work

## What this addresses

This strategy reduces client-side DOM complexity by not rendering a subtree when the current state does not require it.

The supplied evidence shows three evidence-derived forms of the same mechanism:

- **Skip rendering when required state is absent**  
  In `skalenetwork/portal#619`, `CommunityPool` returns `null` when `address` is missing, so the community-pool subtree is not mounted until wallet state exists.
- **Render only the selected detail panel**  
  In `jeong-sik/masc-mcp#8059`, the connector overview/status flow was changed so one connector detail panel is selected at a time instead of rendering multiple competing detail surfaces.
- **Split large navigation into separate desktop and mobile fragments**  
  In `vivid-planet/comet#4235`, header navigation was separated into desktop and mobile fragments, each rendered through its own layout path.

The common mechanism is **omission of unnecessary rendering**, not CSS hiding.

## When to apply / when to skip

### Apply

Use this strategy when all of the following are true:

- A subtree is only meaningful after prerequisite state exists, such as an address, selected item, or active variant.
- Only one variant should be interactive or visible at a time.
- Rendering the full subtree would create unnecessary DOM nodes, reconciliation work, or client-side layout/paint work.
- The UI can safely fall back to an empty state, placeholder, or alternate variant without losing required behavior.

### Skip

Do not use this strategy when any of the following are true:

- The subtree must remain mounted for state preservation, measurement, or continuity.
- The content is required for accessibility or navigation in all states.
- The gating state is not stable enough to decide whether the subtree should exist.
- You only need visual hiding; the evidence supports omission of rendering, not a generic visibility toggle.

## Required validation

### `address_present_for_subtree`

**Evidence:** `skalenetwork/portal#619` adds `if (!address) return null;` in `CommunityPool`.

**What to validate:**

- The component has a concrete prerequisite state.
- The subtree is not rendered when that state is absent.
- The gated subtree is mounted only after the prerequisite becomes available.

**Measurable check:**

- Render the component with the prerequisite state absent and confirm the subtree root is not present in the DOM.
- Render again with the prerequisite state present and confirm the subtree root appears.

### `selected_variant_is_known`

**Evidence:** `jeong-sik/masc-mcp#8059` and `vivid-planet/comet#4235` both select one active surface from a finite set of known variants.

**What to validate:**

- The UI has a finite set of supported variants.
- Selection resolves to one of those variants, not an arbitrary string.
- Only the chosen variant is rendered as the active detail/navigation surface.

**Measurable check:**

- Provide a known variant identifier and confirm the corresponding surface is selected.
- Provide an unsupported identifier and confirm the UI falls back to a defined default or no selection, rather than rendering an invalid branch.

### `required_state_is_available`

**Evidence:** `skalenetwork/portal#619` and `jeong-sik/masc-mcp#8059` both gate rendering on state such as wallet address, connector availability, or selection.

**What to validate:**

- The state needed to render the subtree is actually available and usable.
- The subtree does not render in a partially initialized state that would force placeholder-heavy DOM.
- The rendered branch corresponds to the current state rather than a stale or default branch.

**Measurable check:**

- Confirm the prerequisite state is populated before rendering the gated subtree.
- Confirm the rendered branch matches the current state after selection or state change.
- Confirm no extra detail subtree remains mounted when the state changes to a different valid branch.

## Recommended approaches

### 1) Return `null` when the prerequisite state is absent

This is the clearest evidence-backed shape from `skalenetwork/portal#619`.

```tsx
function CommunityPool() {
  const { address } = useAccount()

  if (!address) return null

  return (
    <section>
      {/* subtree only exists when address is present */}
    </section>
  )
}
```

### 2) Render one selected detail surface instead of all detail surfaces

This matches the selected-detail behavior in `jeong-sik/masc-mcp#8059`.

```tsx
function ConnectorStatusPanel() {
  const [selectedConnectorId, setSelectedConnectorId] = useState<
    'discord' | 'imessage' | 'slack' | 'telegram'
  >('discord')

  return (
    <>
      <ConnectorOverviewStrip
        selectedConnectorId={selectedConnectorId}
        onSelectConnector={setSelectedConnectorId}
      />
      <ConnectorDetailPanel connectorId={selectedConnectorId} />
    </>
  )
}
```

### 3) Split layout-specific fragments so only the relevant subtree is mounted

This follows the desktop/mobile fragment split in `vivid-planet/comet#4235`.

```tsx
function Header({ header }: { header: HeaderFragment }) {
  return (
    <header>
      <DesktopMenu menu={header} />
      <MobileMenu menu={header} />
    </header>
  )
}
```

The evidence supports this as a structural separation pattern when the two fragments serve different layout paths.

## Good examples

These examples are evidence-derived from the supplied patches.

### Good: omit the subtree until required state exists

- `CommunityPool` returns `null` when `address` is absent.
- Result: the community-pool subtree is not rendered until the prerequisite state exists.

### Good: render a single selected detail panel

- The connector overview/status flow keeps one selected detail panel active.
- Result: the UI avoids mounting multiple competing detail surfaces at once.

### Good: separate desktop and mobile navigation fragments

- Header navigation is split into `DesktopMenu` and `MobileMenu`.
- Result: each layout path renders only the subtree it needs.

## Bad examples

These are anti-patterns only in the sense that they would defeat the strategy described by the evidence.

### Bad: render the subtree before prerequisite state exists

```tsx
function CommunityPool() {
  const { address } = useAccount()

  return (
    <section>
      {address ? <CommunityPoolBody /> : <CommunityPoolBody />}
    </section>
  )
}
```

Why this is bad: the subtree is rendered regardless of whether the prerequisite state is present, so DOM complexity is not reduced.

### Bad: mount multiple competing detail surfaces at once

```tsx
function ConnectorStatusPanel() {
  return (
    <>
      <DiscordDetail />
      <IMessagesDetail />
      <SlackDetail />
      <TelegramDetail />
    </>
  )
}
```

Why this is bad: all detail subtrees remain mounted even though only one is needed at a time.

### Bad: keep both layout variants mounted without need

```tsx
function Header({ header }: { header: HeaderFragment }) {
  return (
    <>
      <DesktopMenu menu={header} />
      <MobileMenu menu={header} />
    </>
  )
}
```

Why this is bad: if both variants are mounted simultaneously without a gating reason, the page carries unnecessary DOM and reconciliation work.

## How to verify

Use the same measurement signals named in the evidence:

- Lighthouse DOM size
- Lighthouse DOM size / TBT
- Lighthouse DOM size / main-thread work
- DOM size / main-thread work

### Verification steps

1. Measure the page in the state that previously rendered the larger subtree.
2. Apply the conditional rendering or variant selection.
3. Measure the same page and state again.
4. Confirm one of the following:
   - the gated branch no longer contributes DOM when the prerequisite state is absent, or
   - only one selected variant is mounted at a time.

### What to record

- The state used for the measurement.
- The subtree that is omitted or narrowed.
- The DOM-size metric before and after.
- The main-thread metric before and after.

### Acceptance criteria

- The gated subtree is absent when the prerequisite state is absent.
- The selected variant is one of the known supported variants.
- Only the active detail/navigation surface is mounted for the current state.
- The measurement is repeatable for the same page state.

Do not assume a fixed improvement. The evidence supports directional reduction in DOM and associated client work, but the supplied packet does not provide numeric deltas.

## Evidence and confidence

### Observed facts

- `skalenetwork/portal#619` adds an early return in `CommunityPool` when `address` is absent, preventing the subtree from rendering.
- `jeong-sik/masc-mcp#8059` changes the connector overview/status flow so a single selected detail panel is rendered and switched by tile selection.
- `vivid-planet/comet#4235` separates header navigation into desktop and mobile fragments, each with its own rendering path.
- The regression evidence supports reducing rendered markup and host-element work by avoiding unnecessary props or redundant attributes, but it does not establish a broader universal rule beyond reducing unnecessary rendered content.

### Inference

- Conditional rendering can reduce DOM size and related main-thread work because fewer nodes are mounted and reconciled.
- The strategy is safest when the omitted subtree is genuinely optional and can be reconstructed from current state.
- The pattern generalizes across the supplied sources because each source removes or narrows a rendered branch based on state or variant.

### Confidence

Medium. The mechanism is consistent across three repositories, but the packet does not provide numeric measured deltas, so the playbook should remain conditional and measurement-driven.

## Risks and limitations

- Removing a subtree can discard local UI state unless that state is intentionally derived or preserved elsewhere.
- A gated branch may need an alternate empty or placeholder state to avoid confusing users when the prerequisite is absent.
- Variant selection must remain deterministic; otherwise the UI can appear to jump between branches.
- The evidence supports conditional omission of unnecessary subtrees, not blanket removal of all hidden or secondary UI.
- No universal browser-support or percentage claims are justified by the supplied evidence.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: dom-complexity--conditional-rendering-to-avoid-unnecessary-subtree`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
