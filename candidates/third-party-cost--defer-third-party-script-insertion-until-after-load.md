---
issue_type: third-party-cost--defer-third-party-script-insertion-until-after-load
parent_strategy: third-party-cost
risk_tier: low
cwv_metrics:
  - Lighthouse third-party script cost
  - Lighthouse JavaScript payload
  - Lighthouse performance third-party impact
  - Lighthouse performance TBT
source_prs:
  - Unleash/unleash#10489
  - greenpeace/planet4-master-theme#2738
  - juanequis/juanx#20
  - pulumi/docs#18126
required_validation:
  - third_party_script_is_not_enqueued_globally
  - third_party_script_is_inserted_only_after_window_load
  - feature_scoped_third_party_usage_is_preserved
forbidden_techniques: []
---

# Defer third-party script insertion until after load

> **Risk tier:** low · **Parent strategy:** third-party-cost · **CWV metrics:** Lighthouse third-party script cost, Lighthouse JavaScript payload, Lighthouse performance third-party impact, Lighthouse performance TBT

## What this addresses

This strategy reduces third-party cost by avoiding unconditional delivery and execution of scripts or libraries on pages that do not need them.

The supplied evidence supports two related mechanisms:

1. **Remove global enqueue paths** for third-party libraries when the library is only needed by a specific feature.
2. **Insert third-party scripts after `window.load`** or use an equivalent deferred-loading mechanism for non-critical scripts.
3. **Keep third-party usage feature-scoped** so pages without the feature do not pay the cost.

## Evidence summary

Observed changes across four repositories show consistent directional improvement:

- `greenpeace/planet4-master-theme#2738` removed global enqueue paths for `hammerjs` and `rellax`, and moved those dependencies into feature-local imports.
- `pulumi/docs#18126` deferred GitHub buttons and consent-manager script insertion until `window.load`.
- `juanequis/juanx#20` used lazy-loading for Cookiebot and Google Analytics scripts.
- `Unleash/unleash#10489` removed third-party script/widget loading from the documentation configuration and related client bootstrap paths, reducing always-on third-party delivery.

The evidence packet reports:
- **4 observations across 4 repositories**
- **100.0% directional consistency**
- **4 improvements, 0 regressions**
- **no absolute measured delta summary available**

## Apply / skip

### Apply when

- a third-party library is only needed by one feature, block, or component
- a script is currently loaded globally but only some pages use the feature
- the script can wait until after the page load event without breaking the feature
- the feature can tolerate deferred initialization or user-triggered loading

### Skip when

- the third-party script is required for initial rendering or critical above-the-fold behavior
- the feature depends on the script before `load` for correctness
- the code path is already feature-scoped and there is no global delivery to remove
- the evidence does not show a safe way to defer the script without changing behavior

## Required validation

### `third_party_script_is_not_enqueued_globally`

**What to validate:** the third-party script is no longer added from a global enqueue or global head-injection path.

**Why this matters:** global delivery causes the script to be requested on pages that do not use the feature, increasing third-party cost and JavaScript payload.

**Evidence-derived checks:**
- In `greenpeace/planet4-master-theme#2738`, the global `wp_enqueue_scripts` hook that enqueued `rellax` was removed from `src/Loader.php`.
- In the same PR, the block-specific `wp_enqueue_script('hammer', ...)` calls were removed from `src/Blocks/CarouselHeader.php` and `src/Blocks/Gallery.php`.

**Pass condition:**
- no site-wide enqueue or head injection remains for the third-party script
- any remaining inclusion is tied to the feature/component that needs it

### `third_party_script_is_inserted_only_after_window_load`

**What to validate:** the script is created, appended, or activated only after the `load` event, or via an equivalent deferred-loading mechanism supported by the evidence.

**Why this matters:** post-load insertion avoids competing with the initial HTML parse and early page work.

**Evidence-derived checks:**
- In `pulumi/docs#18126`, `buttons.js` and `consent-manager.js` are appended inside `window.addEventListener('load', ...)`.
- In `juanequis/juanx#20`, `Script` entries use `strategy="lazyOnload"` for Cookiebot and Google Analytics.

**Pass condition:**
- the script is not requested during the initial HTML parse when the supported pattern is post-load insertion
- the deferred path still initializes the feature when the page is ready

### `feature_scoped_third_party_usage_is_preserved`

**What to validate:** the feature still imports or initializes the third-party library where it is actually used.

**Why this matters:** deferral should not remove required behavior from the feature itself.

**Evidence-derived checks:**
- In `greenpeace/planet4-master-theme#2738`, `Hammer` and `Rellax` are imported in the component/module that uses them.
- The carousel and parallax logic remain in the feature files rather than being globally bootstrapped.

**Pass condition:**
- the feature still works when the relevant block/component is present
- the library is reachable from the feature code path, not from a site-wide loader

## Recommended approaches

Prefer one of these evidence-backed shapes.

### 1) Move the third-party import into the feature module

Supported by the `hammerjs` and `rellax` changes in `greenpeace/planet4-master-theme#2738`.

**Good**
```js
import Hammer from 'hammerjs';

export const GalleryCarousel = ({images, onImageClick, isEditing}) => {
  // feature-local use of Hammer
};
```

### 2) Remove the global enqueue and let the feature own the dependency

Supported by the removal of the global `wp_enqueue_scripts` hook in `src/Loader.php`.

**Good**
```php
public static function enqueue_frontend_assets(): void
{
    parent::enqueue_frontend_assets();
}
```

### 3) Append the third-party script after `window.load`

Supported by `pulumi/docs#18126`.

**Good**
```html
<script>
  window.addEventListener('load', function() {
    var s = document.createElement('script');
    s.src = 'https://buttons.github.io/buttons.js';
    document.body.appendChild(s);
  });
</script>
```

### 4) Use a lazy-loading strategy for non-critical third-party scripts

Supported by `juanequis/juanx#20`.

**Good**
```tsx
<Script
  src="https://www.googletagmanager.com/gtag/js?id=G-9M7VTY6DJL"
  strategy="lazyOnload"
/>
```

## Good / bad examples

### Good: feature-scoped import
```js
import Hammer from 'hammerjs';

const carouselHeadHammer = new Hammer(carouselElement, {recognizers: []});
```

### Good: post-load insertion
```html
<script>
  window.addEventListener('load', function() {
    var s = document.createElement('script');
    s.src = '/js/consent-manager.js';
    document.body.appendChild(s);
  });
</script>
```

### Good: lazy-loaded non-critical script
```tsx
<Script
  id="google-analytics"
  strategy="lazyOnload"
>
  {`
    window.dataLayer = window.dataLayer || [];
  `}
</Script>
```

### Bad: global or early insertion
The supplied evidence does not justify a reusable anti-pattern regex or a universal bad-code template. The supported inference is only that global or early insertion increases third-party cost when the script is not needed on every page.

## How to verify

Use the same measurement family associated with this strategy:

- Lighthouse third-party script cost
- Lighthouse JavaScript payload
- Lighthouse performance third-party impact
- Lighthouse performance TBT

### Verification method

Compare before and after on the same page types:

1. pages with the feature present
2. pages without the feature present

### Pass criteria

- reduced third-party script cost on pages that no longer load the feature
- reduced JavaScript payload where the third-party library was previously global
- no regression in feature behavior when the feature is present
- no reliance on a fixed improvement amount; the evidence supports directional improvement only

## Evidence and confidence

### Observed facts

- `greenpeace/planet4-master-theme#2738` removed global `hammerjs` and `rellax` enqueue paths and moved those dependencies into feature-local imports.
- `pulumi/docs#18126` deferred GitHub buttons and consent-manager script insertion until `window.load`.
- `juanequis/juanx#20` used lazy-loading for Cookiebot and Google Analytics scripts.
- `Unleash/unleash#10489` removed always-on third-party script/widget loading from documentation configuration and client bootstrap paths.
- The supplied summary reports 4 observations across 4 repositories with 100% directional consistency and no regressions.

### Inference

- Deferring third-party insertion until after load is a safe low-risk optimization when the script is not required for initial rendering.
- Feature-scoped loading is the key mechanism for avoiding unnecessary delivery on pages that do not use the feature.

### Confidence

**Medium.** The direction is consistent across the supplied evidence, but the packet does not include numeric deltas or a broad set of failure cases.

## Risks and limitations

- Deferring a script can break behavior if the script is needed before `load`; do not apply this strategy to critical rendering dependencies.
- Some third-party widgets may require additional initialization after deferred insertion; the evidence supports the pattern, not a universal wrapper.
- Moving a dependency into feature code can still leave the library in the bundle for pages that include the feature; the benefit is avoiding delivery on pages without it.
- The evidence supports post-load insertion and feature scoping, but not a universal rule for all third-party resources.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (4 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **4 observations across 4 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: third-party-cost--defer-third-party-script-insertion-until-after-load`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
