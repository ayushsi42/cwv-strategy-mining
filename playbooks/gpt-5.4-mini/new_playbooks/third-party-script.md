---
issue_type: third-party-script
applicable_flavors:
- cs
- ams
- headless
risk_tier: medium
required_validation:
- third_party_host_allowlisted
- csp_allows_external_origin
- asset_is_not_aem_managed_copy
- no_local_bundle_equivalent_exists
forbidden_techniques:
- pattern: <script\s+[^>]*src\s*=\s*["']https?://[^"'>]*(cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com)[^"'>]*["'][^>]*>
  reason: Don't add a new external CDN script tag without validating CSP, SRI, and
    the performance tradeoff against a local AEM-managed asset
- pattern: <link\s+[^>]*rel\s*=\s*["']stylesheet["'][^>]*href\s*=\s*["']https?://[^"'>]*(cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com)[^"'>]*["'][^>]*>
  reason: Don't add a new external CDN stylesheet without validating CSP, SRI, and
    the performance tradeoff against a local AEM-managed asset
- pattern: integrity\s*=\s*["'][^"'>]+["'][^>]*>\s*$
  reason: Don't rely on SRI alone as the fix; external delivery still adds a third-party
    dependency and network variability
source_prs:
- marble-systems/front-end-capstone#6
- martincostello/dependabot-helper#210
- martincostello/website#1087
- bcgov/cirmo-dpia#442
---
# Third-party script

> **Risk tier:** medium · **Applies to:** CS, AMS, Headless · **CWV metric:** LCP, TBT

## What this addresses

This issue covers introducing or switching to third-party CDN-delivered CSS/JS for a library such as Bootstrap instead of serving it from the application or AEM clientlibs. External delivery can change request priority, connection setup, and cache behavior, which can indirectly affect LCP and TBT.

## When to apply / when to skip
**Apply when:**
- A page is loading a library from a third-party origin such as a CDN
- The change replaces a local bundle or clientlib with an external `<script>` or `<link>`
- The host is already approved in CSP and the team accepts the operational dependency
- The asset is static and shared across many pages, making the CDN tradeoff plausible

**Skip when:**
- The library can be bundled into AEM clientlibs or served from the same origin with no meaningful cost increase
- The external host is not allowlisted in CSP or cannot be validated with SRI
- The resource is page-specific and would require repeated per-template CDN wiring
- The change is for EDS, where this playbook does not apply

## Recommended approaches

### Prefer AEM-managed delivery for stable UI libraries

Serve the library from AEM clientlibs or the application itself when the asset is part of the site shell and not truly external.

```xml
<!-- Good: clientlib folder -->
<jcr:root
    jcr:primaryType="cq:ClientLibraryFolder"
    categories="[site.bootstrap]"
    dependencies="[site.base]" />
```

```html
<!-- Good: include the local clientlib -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html">
  <sly data-sly-call="${clientlib.css @ categories='site.bootstrap'}" />
  <sly data-sly-call="${clientlib.js @ categories='site.bootstrap'}" />
</sly>
```

Keeping the asset local avoids third-party connection setup and makes caching, versioning, and rollback easier to control within AEM.

### If a CDN is required, keep it explicit and policy-aligned

```html
<!-- Good: external asset with explicit policy and SRI -->
<link rel="preconnect" href="https://cdnjs.cloudflare.com" crossorigin>
<link rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.0/css/bootstrap.min.css"
      crossorigin="anonymous"
      referrerpolicy="no-referrer">
<script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.0/js/bootstrap.bundle.min.js"
        crossorigin="anonymous"
        referrerpolicy="no-referrer"></script>
```

This works when the CDN is a deliberate architecture choice, not an accidental shortcut. Preconnect reduces some overhead, but it does not remove the third-party dependency.

## Anti-patterns

### Replacing a local asset with a CDN tag without validating the dependency

```html
<!-- Bad -->
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.1/dist/css/bootstrap.min.css">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.1/dist/js/bootstrap.bundle.min.js"></script>
```

**Why this is bad:** It introduces a third-party network dependency into the critical path without proving that CSP, caching, and render timing are acceptable.

### Adding a CDN asset but omitting policy controls

```html
<!-- Bad -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.0/js/bootstrap.bundle.min.js"></script>
```

**Why this is bad:** Without CSP alignment, the page is more fragile and the browser has less protection against unexpected third-party changes.

### Using a CDN when the same library can be served locally

```html
<!-- Bad -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.2.0/css/bootstrap.min.css">
```

**Why this is bad:** For AEM sites, a local clientlib is usually more controllable and avoids third-party connection setup that can delay first render.

## Flavor-specific notes

### CS

Prefer clientlibs for Bootstrap and related UI assets. If the library is used across multiple templates, create a dedicated clientlib category and include it only where needed rather than wiring a CDN into the shared page shell.

### AMS

If the site already uses dispatcher-cached static assets, serving Bootstrap from the application or clientlibs is usually easier to govern than relying on a CDN. If a CDN is retained, verify the dispatcher and CSP configuration together so the external origin does not become a hidden production dependency.

### Headless

This applies when the headless app is still browser-rendered and the page shell loads external CSS/JS. Keep the external dependency explicit, and prefer a local build artifact when the library is part of the app’s baseline UI rather than a truly shared third-party service.