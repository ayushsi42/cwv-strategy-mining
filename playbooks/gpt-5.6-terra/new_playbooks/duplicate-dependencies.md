---
issue_type: duplicate-dependencies
applicable_flavors:
- eds
- cs
- headless
risk_tier: high
required_validation: []
forbidden_techniques: []
source_prs:
- ecadlabs/taquito#3230
- BuilderIO/builder#1253
- nextcloud/nextcloud-password-confirmation#477
- tsuki-lab/microcms-ts-sdk#34
- AudiusProject/audius-protocol#6493
- equinor/cc-components#541
- justeattakeaway/pie#949
- justeattakeaway/pie#1037
- razorpay/blade#1797
- threlte/threlte#852
- Kong/public-ui-components#1129
- justeattakeaway/pie#1262
- deephaven/deephaven-plugins#449
- Kong/public-ui-components#1579
- ovh/manager#14412
- webex/widgets#359
- recogito/text-annotator-js#192
- edx/frontend-component-header-edx#662
- MetaMask/metamask-design-system#729
- kage1020/react-component-color#4
---
# Duplicate dependencies

## What this addresses

Several evidence PRs externalize dependencies or move them to peer dependencies to avoid including them in library bundles.

In Kong’s `entities-certificates` build, externalizing common dependencies changed the reported artifacts from:

```text
dist/entities-certificates.es.js   504.87 kB │ gzip: 111.05 kB
dist/entities-certificates.umd.js  363.66 kB │ gzip: 94.92 kB
```

to:

```text
dist/entities-certificates.es.js   336.60 kB │ gzip: 69.73 kB
dist/entities-certificates.umd.js  246.57 kB │ gzip: 60.10 kB
```

The same PR moved `@kong-ui-public/entities-shared` and `@kong/icons` from package dependencies to peer and development dependencies.

Externalizing a dependency changes responsibility for providing it. Taquito’s build discussion notes that externalizing `Buffer` would require consumers to configure buffer polyfills themselves, whereas handling it through the package’s polyfill setup simplifies installation and setup.

## When to apply / when to skip
**Apply when:**
- Artifact analysis shows that a dependency is included in a library bundle and the consuming environment is intended to provide that dependency.
- The library can declare and document the dependency as a peer dependency or otherwise provide a supported consumer contract.
- The dependency version and runtime availability are validated in the consuming application.
- The resulting build output is measured before and after the change.

### When to skip

- Externalizing the dependency would require unsupported consumer setup.
- The package must continue to provide the dependency for standalone use.
- The consuming runtime cannot reliably provide a compatible dependency.
- The externalized dependency has required setup that the consumer has not agreed to own.

## Recommended approaches

### Externalize verified shared package dependencies

Configure the library build to exclude dependencies that the consumer is expected to provide, and declare those dependencies appropriately.

Kong’s entity packages externalized `@kong-ui-public/entities-shared` and `@kong/icons` while listing them as peer dependencies and development dependencies.

```json
{
  "peerDependencies": {
    "@example/shared-runtime": "^1.0.0"
  },
  "devDependencies": {
    "@example/shared-runtime": "^1.0.0"
  }
}
```

```js
export default {
  build: {
    rollupOptions: {
      external: ['@example/shared-runtime'],
    },
  },
};
```

Measure the produced artifacts after changing the build configuration.

### Keep dependencies bundled when consumer setup would otherwise be required

Taquito’s discussion identifies `Buffer` as a case where leaving a dependency external would require users to configure buffer polyfills themselves. If a package owns required runtime setup, retaining that setup in the package may provide a simpler consumer installation path.

### Use peer dependencies for commonly shared optional integrations

The Threlte discussion proposes using peer dependencies for `three-mesh-bvh` to reduce bundle size, while noting that this requires additional documentation and setup education. Use this approach only when the consumer contract is explicit.

## Anti-patterns

### Externalizing a dependency without documenting consumer requirements

```js
export default {
  build: {
    rollupOptions: {
      external: ['@example/shared-runtime'],
    },
  },
};
```

**Why this is bad:** The evidence from Taquito notes that externalizing `Buffer` would require consumers to configure buffer polyfills themselves. An externalization decision should state any equivalent consumer setup requirement.

### Moving a dependency to a peer dependency without validating the consuming build

```json
{
  "peerDependencies": {
    "@example/shared-runtime": "^1.0.0"
  }
}
```

**Why this is bad:** The evidence PRs pair externalization with package-manifest changes and build-output review. A peer-dependency change should be validated in the intended consuming application.

### Assuming an externalization reduces bundle size without measuring

```js
export default {
  build: {
    rollupOptions: {
      external: ['@example/shared-runtime'],
    },
  },
};
```

**Why this is bad:** Kong’s reported bundle reduction was measured for particular packages and dependencies. Measure the affected artifacts rather than assuming the same result for every dependency.

## Validation

- Compare generated artifact sizes before and after the change.
- Confirm that externalized dependencies are declared in the package manifest where appropriate.
- Test the package in the consuming application that supplies the external dependency.
- Document any consumer-owned setup, such as required polyfills or peer dependencies.