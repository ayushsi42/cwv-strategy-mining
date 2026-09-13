---
issue_type: optional-component-loading
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation: []
forbidden_techniques: []
source_prs:
- strapi/strapi#14163
- jameel-institute/daedalus-web-app#65
- NASA-IMPACT/veda-ui#1199
- metabrainz/listenbrainz-server#3197
---
# Optional component loading

> **Risk tier:** medium

## What this addresses

Some components are optional because they depend on configuration or user preferences.

The evidence includes:
- A globe feature whose reviewer noted that it would need to be lazy-loaded.
- Banner and cookie-consent components that were identified for lazy loading because they render only when configuration is present.
- A BrainzPlayer feature updated so its code is not loaded when the user has disabled the feature.

## When to apply / when to skip
**Apply when:**
- A component renders only when configuration is present.
- A component can be disabled through a saved user preference.
- The enablement decision is available before the optional component is rendered.

## Recommended approaches

### Load a user-disabled optional block only when enabled

Evaluate the saved preference before loading the optional block implementation. When the saved preference disables the player, do not import or decorate the player.

```javascript
export default async function decorate(block) {
  const preferences = JSON.parse(
    window.localStorage.getItem('user-preferences') || '{}',
  );
  const playerDisabled =
    preferences?.brainzplayer?.brainzplayerEnabled === false;

  if (playerDisabled) {
    block.remove();
    return;
  }

  const { default: decorateBrainzPlayer } = await import('./brainzplayer.js');
  await decorateBrainzPlayer(block);
}
```

Evaluate the saved preference before choosing whether the page includes the optional component.

### Load configuration-controlled components only when configuration is present

The VEDA change identifies Banner and CookieConsent as components to lazy-load because they render only when their configuration exists. Keep the configuration check outside the optional component so the application can avoid loading that component when no applicable configuration is available.

Cookie-consent state can also be checked at session start and when no response has been recorded, as in the evidence PR.

### Consider lazy loading for map features with geodata

The globe PR adds globe behavior and geodata files. Its review discussion notes that lazy loading would be needed. For a globe that is optional, evaluate whether it is enabled before loading its renderer and geodata.

## Anti-patterns

### Statically starting a feature load before checking whether a user has disabled it

**Bad:**

```javascript
const brainzPlayerModule = import('./brainzplayer.js');

export default async function decorate(block) {
  const preferences = JSON.parse(
    window.localStorage.getItem('user-preferences') || '{}',
  );
  const playerDisabled =
    preferences?.brainzplayer?.brainzplayerEnabled === false;

  if (playerDisabled) {
    block.remove();
    return;
  }

  const { default: decorateBrainzPlayer } = await brainzPlayerModule;
  await decorateBrainzPlayer(block);
}
```

**Why this is bad:** The player module begins loading before the saved preference is checked, so its code can be requested even when the feature is disabled.

### Loading configuration-controlled components before checking configuration

**Bad:**

```javascript
const bannerModule = import('./banner.js');
const cookieConsentModule = import('./cookie-consent.js');

export default async function decorate(block) {
  const pageConfig = JSON.parse(block.dataset.pageConfig || '{}');

  if (pageConfig.banner) {
    const { default: decorateBanner } = await bannerModule;
    await decorateBanner(block);
  }

  if (pageConfig.cookieConsent) {
    const { default: decorateCookieConsent } = await cookieConsentModule;
    await decorateCookieConsent(block);
  }
}
```

**Why this is bad:** The Banner and CookieConsent modules begin loading before their configuration is checked, even though they render only when their configurations are present.

### Loading optional globe code before determining whether the globe is needed

**Bad:**

```javascript
const globeRendererModule = import('./globe-renderer.js');
const worldMapDataModule = import('./world-map-data.js');

export default async function decorate(block) {
  if (block.dataset.enabled !== 'true') {
    block.remove();
    return;
  }

  const [{ default: decorateGlobe }, { default: worldMap }] = await Promise.all([
    globeRendererModule,
    worldMapDataModule,
  ]);

  decorateGlobe(block, worldMap);
}
```

**Why this is bad:** The globe implementation and map data begin loading before the enablement check. The globe evidence includes added geodata and review feedback that lazy loading would be needed.

## Implementation notes

- Read the relevant configuration or saved preference before rendering the optional component.
- Use a block-relative dynamic import for optional components when they should not be loaded for disabled users.
- Re-check consent-related state when a session starts and when no response has been recorded, where that matches the application's consent behavior.