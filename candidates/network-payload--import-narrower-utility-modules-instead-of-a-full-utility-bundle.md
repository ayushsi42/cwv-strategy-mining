---
issue_type: network-payload--import-narrower-utility-modules-instead-of-a-full-utility-bundle
parent_strategy: network-payload
risk_tier: low
cwv_metrics: [Lighthouse JS payload, unused JS]
source_prs:
  - hyperlane-xyz/hyperlane-monorepo#7250
  - microsoft/rushstack#5421
  - microsoft/teams.ts#561
  - openremote/openremote#2430
required_validation:
  - narrower_entrypoint_available
  - import_site_uses_narrower_module_or_package_entrypoint
forbidden_techniques: []
---

# Import narrower utility modules instead of a full utility bundle

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metrics:** Lighthouse JS payload, unused JS

## What this addresses

This strategy reduces shipped JavaScript by replacing a broad utility import with a narrower package entrypoint or a more specific module. The observed mechanism is that importing only the needed utility surface can shrink the dependency graph, which lowers bytes downloaded and parsed by the browser.

## When to apply / when to skip

**Apply when:**
- a file imports a broad utility bundle but uses only a small subset of its exports
- the same symbol is available from a narrower package or package entrypoint
- the change can be made without changing runtime behavior or public API shape
- the repository already exposes a dedicated package or entrypoint for the needed utility

**Skip when:**
- the narrower entrypoint does not exist or does not export the needed symbol
- the import is already minimal and there is no narrower supported source
- the change would require inventing a new package boundary without evidence
- the import is used for shared runtime behavior that is intentionally centralized in the broader package

## Required validation

### `narrower_entrypoint_available`

Confirm that the needed symbol is exported by a narrower package or entrypoint that is already present in the repository or package set.

**How to validate:**
- verify the narrower package or entrypoint exists in the dependency graph or package metadata
- verify the symbol is exported from that narrower source
- verify the consumer no longer needs the broader package for that symbol

### `import_site_uses_narrower_module_or_package_entrypoint`

Confirm the consuming code now imports the symbol from the narrower source rather than the broad bundle.

**How to validate:**
- inspect the changed import statement in the consumer file
- confirm the old broad import was removed for the moved symbol
- confirm the new import path is the narrower package or package entrypoint

## Evidence-derived patterns

The supplied evidence shows four distinct forms of narrowing:

1. **Move a symbol from a broad utility package to a dedicated package**
   - Hyperlane moved `MinimumRequiredGasByAction`, `GasAction`, `ProtocolType`, `AltVM`, and related types from `@hyperlane-xyz/utils` to `@hyperlane-xyz/provider-sdk`.
   - Rush extracted `CredentialCache` into `@rushstack/credential-cache` so consumers could reference it directly instead of pulling in the larger umbrella package.

2. **Replace a deep subpath import with the package root when the root exports the needed symbol**
   - Microsoft Teams replaced `@microsoft/teams.common/logging` with `@microsoft/teams.common` for `ConsoleLogger`.
   - Microsoft Teams also replaced `@microsoft/teams.common/storage` with `@microsoft/teams.common` for `LocalStorage`.

3. **Replace a broad utility bundle with a per-function package**
   - OpenRemote replaced `lodash` imports with `lodash.transform` and `lodash.debounce`.

4. **Update the consumer dependency set to include the narrower package**
   - Hyperlane added `@hyperlane-xyz/provider-sdk` to the consumer package.
   - Rush added `@rushstack/credential-cache` to the relevant package graphs.

## Good examples

### Good: move a symbol to a narrower package

```ts
import { GasAction, ProtocolType } from '@hyperlane-xyz/provider-sdk';
import { assert } from '@hyperlane-xyz/utils';
```

**Why this is good:** the evidence shows these symbols were moved out of `@hyperlane-xyz/utils` and into `@hyperlane-xyz/provider-sdk`, leaving only the remaining utility import in the broader package.

### Good: use the package root instead of a deeper subpath

```ts
import { ConsoleLogger } from '@microsoft/teams.common';
```

**Why this is good:** the evidence shows `ConsoleLogger` was imported from the package root rather than `@microsoft/teams.common/logging`.

### Good: use a per-function package

```ts
import transform from 'lodash.transform';
```

**Why this is good:** the evidence shows a broad `lodash` import was replaced with the narrower `lodash.transform` package.

### Good: use a per-function package

```ts
import debounce from 'lodash.debounce';
```

**Why this is good:** the evidence shows a broad `lodash` import was replaced with the narrower `lodash.debounce` package.

### Good: reference an extracted package directly

```ts
import { CredentialCache } from '@rushstack/credential-cache';
```

**Why this is good:** the evidence shows the API was extracted into a dedicated package so consumers could depend on it directly.

## Bad examples

### Bad: keep importing from the broad utility bundle when a narrower package exists

```ts
import { debounce } from 'lodash';
```

**Why this is bad:** the evidence shows this was replaced by `lodash.debounce`, indicating the broader bundle was not the preferred payload-reduction path.

### Bad: keep using a deeper subpath when the package root exports the symbol

```ts
import { ConsoleLogger } from '@microsoft/teams.common/logging';
```

**Why this is bad:** the evidence shows the import moved to `@microsoft/teams.common`.

### Bad: keep using the broader utility package for a symbol that was extracted

```ts
import { MinimumRequiredGasByAction } from '@hyperlane-xyz/utils';
```

**Why this is bad:** the evidence shows this symbol was moved to `@hyperlane-xyz/provider-sdk`.

## How to verify

Use the same CWV-relevant measurements that motivated the strategy:

- inspect **Lighthouse JS payload**
- inspect **Lighthouse unused JS**

Verification should be measurable at the page or bundle level:

1. Record a baseline build or page load.
2. Apply the import narrowing change.
3. Rebuild and rerun Lighthouse.
4. Confirm that JS payload or unused JS does not increase, and preferably decreases.
5. Confirm the changed module graph no longer pulls the broader utility bundle for the moved symbol.

For package-extraction cases, also verify that:
- the consumer depends on the extracted package directly
- the umbrella package is no longer required for the moved API
- the narrower package exports the exact symbol used by the consumer

## Evidence and confidence

### Observed facts

- Hyperlane replaced several imports from `@hyperlane-xyz/utils` with imports from `@hyperlane-xyz/provider-sdk`.
- Hyperlane added `@hyperlane-xyz/provider-sdk` to the consumer package.
- Microsoft Teams replaced `@microsoft/teams.common/logging` with `@microsoft/teams.common`.
- Rush extracted `CredentialCache` into `@rushstack/credential-cache` and updated consumers to reference it directly.
- OpenRemote replaced `lodash` imports with narrower packages such as `lodash.transform` and `lodash.debounce`.

### Inference

- Narrower imports can reduce shipped JavaScript by shrinking the transitive dependency surface.
- The strategy is most appropriate when the narrower source is already exported and the edit is a direct import-path substitution rather than a behavioral refactor.

### Confidence

Medium. The evidence is consistent across four repositories and shows 100% directional consistency, but the supplied packet does not include fixed measured deltas.

## Risks and limitations

- A narrower import is only safe if it exports the exact symbol and preserves the expected runtime semantics.
- Some umbrella packages intentionally centralize shared behavior; splitting imports without a supported extraction can create maintenance or compatibility issues.
- This strategy does not guarantee a measurable CWV win in every case; the benefit depends on how much code the narrower source actually removes from the shipped bundle.
- If the broader package is still needed elsewhere in the same module, the net payload reduction may be limited.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (4 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **4 observations across 4 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: network-payload--import-narrower-utility-modules-instead-of-a-full-utility-bundle`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
