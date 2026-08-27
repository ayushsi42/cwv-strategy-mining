---
issue_type: layout-stability--reserve-space-only-when-async-content-will-actually-appear
parent_strategy: layout-stability
risk_tier: low
cwv_metrics: [CLS]
source_prs:
  - Freakandi/ha-pp-reader#579
  - aemsites/idfc#522
  - aemsites/idfc#603
  - argos-ci/argos#2051
  - dailydotdev/apps#4864
required_validation:
  - async_content_is_gated_by_presence
forbidden_techniques: []
---
# Reserve space only when async content will actually appear

> **Risk tier:** low · **Parent strategy:** layout-stability · **CWV metric:** CLS

## What this addresses

This strategy reduces layout shifts caused by content that appears later or is revealed conditionally, but only when that content is actually expected to appear.

The evidence supports three related mechanisms:

- **Gate the UI on data presence** so a component is not inserted into the layout until the triggering state exists.
- **Hide deferred blocks on first paint** when they are intentionally revealed later by interaction.
- **Reserve height for a container or placeholder** only for content that will expand into that space, so the eventual reveal does not push surrounding content.

Observed examples include:
- showing an opportunity button only when an alert ID exists,
- hiding bell sections and hotspot blocks until the user can legitimately reveal them,
- reserving min-height for a hotspot wrapper and its block content,
- keeping review and filter state stable while visible subsets change.

## When to apply / when to skip

**Apply when:**
- a component is conditionally rendered from async data or alert state;
- a section is intentionally hidden on first paint and shown later by user action;
- a deferred block needs a stable placeholder or reserved height before reveal;
- a list, hotspot, modal trigger, or overlay would otherwise appear late and shift nearby content.

**Skip when:**
- the content must be visible immediately for editing, preview, or authoring contexts;
- the content is not actually deferred and already participates in initial layout;
- there is no concrete trigger showing that the content will eventually appear;
- you would need to invent a fixed placeholder size without implementation support.

## Required validation

### `async_content_is_gated_by_presence`
Validate that the content is only rendered or shown when the relevant async state exists.

What to check:
- a boolean or equivalent presence check derived from async data, alert state, or completion state;
- the gated component is not rendered when that presence check is false;
- the same content is rendered when that presence check is true.

How to verify:
- inspect the conditional branch or early return that suppresses rendering;
- confirm the presence signal comes from a concrete source such as alerts, completion state, or loaded metadata;
- confirm the reveal path still exists when the signal becomes true or the user performs the triggering action.

Supported evidence-derived patterns:
- `hasOpportunityAlert && isMobile && <JobOpportunityButton />`
- `hasOpportunityAlert && !isMobile && <JobOpportunityButton />`
- `checkHasCompleted(ActionType.OpportunityWelcomePage) ? ... : ...`
- `if (!modalContent) { return; }`
- `if (blockId !== sectionData.firstBlockId) { block.style.display = 'none'; }`

## Recommended approaches

Prefer one of these evidence-backed shapes:

1. **Gate the component on data presence**
   - Do not render the late content until the async signal exists.
   - This is the cleanest option when the content is optional.

2. **Hide the deferred block initially, then reveal it on the user action that legitimately triggers it**
   - Use this when the content is intentionally deferred until interaction.
   - Keep the reveal path explicit and tied to the interaction that makes the content relevant.

3. **Reserve space on the wrapper and the immediate content container**
   - Use this when the deferred block is known to expand into a stable region.
   - The evidence shows reserving both the wrapper and the block content can prevent wrapper-level CLS.

## Good examples

### Gate optional UI on presence

```tsx
const hasOpportunityAlert = !!alerts.opportunityId;

return (
  <>
    {hasOpportunityAlert && !isMobile && <JobOpportunityButton />}
    <FeedSettingsButton onClick={onClick} size={ButtonSize.Medium} />
  </>
);
```

### Reserve space for a deferred block that will actually appear

```js
const blockHeight = block.offsetHeight;
if (blockHeight > sectionData.maxHeight) {
  sectionData.maxHeight = blockHeight;
  if (sectionWrapper) {
    sectionWrapper.style.minHeight = `${sectionData.maxHeight}px`;
    const blockContent = block.closest('.block-content');
    if (blockContent) {
      blockContent.style.minHeight = `${sectionData.maxHeight}px`;
    }
  }
}

block.style.display = 'none';
if (blockId !== sectionData.firstBlockId) {
  block.setAttribute('aria-hidden', 'true');
}
```

### Skip work when the deferred content is not available

```js
if (!modalContent) {
  return;
}
```

## Bad examples

### Rendering optional UI without checking whether it exists

```tsx
<JobOpportunityButton />
```

Why this is bad:
- the evidence supports rendering the button only when the alert state exists;
- unconditional rendering can introduce layout changes when the surrounding state is not ready.

### Revealing deferred content without a concrete trigger

```js
block.style.display = 'block';
```

Why this is bad:
- the evidence shows deferred content should be hidden initially and revealed only on the relevant interaction or presence signal;
- revealing it without that signal can create avoidable layout shifts.

### Reserving space for content that may never appear

```js
sectionWrapper.style.minHeight = '400px';
```

Why this is bad:
- the evidence supports reserving space only when the content is known to expand into that region;
- a hard-coded placeholder without a validated trigger can leave empty gaps.

## How to verify

Use the same metric family observed in the evidence: **CLS**.

Before change:
- observe layout shifts when deferred content appears, expands, or is inserted after initial paint.

After change:
- confirm the gated content does not render until its presence condition is true;
- confirm the reserved container or hidden block does not cause surrounding content to jump when it becomes visible;
- confirm the page still reveals the content when the triggering async state or interaction occurs.

Verification should be measurable:
- compare before/after CLS in a lab run or field trace on the affected interaction path;
- inspect the DOM to confirm the gated element is absent before the presence signal and present after it;
- confirm any reserved wrapper height matches the actual revealed content path rather than a guessed size.

Do not assume a fixed CLS improvement. Verify by comparing before/after behavior on the affected path.

## Evidence and confidence

### Observed facts
- `dailydotdev/apps#4864` gates a job opportunity button on `alerts.opportunityId`, preventing the button from rendering unless the alert exists.
- `Freakandi/ha-pp-reader#579` hides or stabilizes dashboard and detail-table UI to avoid selection and hover artifacts around deferred content.
- `aemsites/idfc#522` hides bell sections on normal pages to prevent CLS, while explicitly allowing them in editing and preview contexts.
- `aemsites/idfc#603` collapses a hero and reveals hotspot content only on the relevant click path, with the first hotspot hidden initially to prevent CLS.
- `argos-ci/argos#2051` keeps filter/search state stable while filtering diffs and preserves the full diff set for review progression, reducing layout churn from changing visible subsets.

### Inference
- The shared mechanism is not “reserve space everywhere”; it is “only allocate or reveal layout for content that is actually going to appear.”
- The safest implementation is conditional rendering or explicit reveal logic tied to a validated presence signal.

### Confidence
- Medium, because the evidence is consistent across multiple repositories and implementations, but measured deltas were not provided and the exact reserved-space sizing rules are context-specific.

## Risks and limitations

- Over-reserving space can create empty gaps if the content never appears.
- Hiding content too aggressively can break editing, preview, or accessibility flows; the evidence explicitly exempts authoring and preview contexts in one source.
- If the reveal trigger is wrong or incomplete, the content may never appear.
- This strategy is only justified when the content’s eventual appearance is supported by a concrete async or interaction signal.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (5 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **7 observations across 6 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: layout-stability--reserve-space-only-when-async-content-will-actually-appear`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
