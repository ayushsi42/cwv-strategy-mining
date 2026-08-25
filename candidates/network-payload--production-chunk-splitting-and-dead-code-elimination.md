---
issue_type: network-payload--production-chunk-splitting-and-dead-code-elimination
parent_strategy: network-payload
risk_tier: low
cwv_metrics:
  - Lighthouse JavaScript
  - Lighthouse Total Blocking Time
  - Lighthouse unused JavaScript
source_prs:
  - yuuttana1223/web-speed-hackathon-2026#13
  - expressjs/expressjs.com#2213
  - gxcsoccer/AlphaArena#516
required_validation:
  - production_build_mode_enabled
  - development_scaffolding_removed_from_shipped_bundle
  - dead_code_elimination_enabled_in_bundler
  - optional_large_dependency_isolated_or_removed_from_critical_bundle
forbidden_techniques: []
---

# Production chunk splitting and dead-code elimination

> **Risk tier:** low · **Parent strategy:** network-payload · **CWV metrics:** Lighthouse JavaScript, Lighthouse Total Blocking Time, Lighthouse unused JavaScript

## What this addresses

This strategy reduces shipped JavaScript by making the production bundle behave like a production bundle:

- build in production mode instead of development mode
- remove development-only bundle scaffolding from shipped output
- enable bundler optimizations that prune unused exports and concatenate modules
- isolate large optional dependencies into separate chunks when they are not needed on the critical path

The evidence across the supplied PRs is consistent with one mechanism: less code is downloaded, parsed, and executed, which can reduce JavaScript payload, unused JavaScript, and main-thread work.

## When to apply / when to skip

### Apply when

- the client bundle is still being built with development settings
- the shipped output includes development-only runtime or debug scaffolding
- the bundler is not using production optimizations such as minification, module concatenation, or used-export analysis
- a large dependency can be isolated into a separate chunk or removed from the critical bundle without changing required initial behavior
- Lighthouse shows unused JavaScript or JavaScript-heavy main-thread work on the affected page

### Skip when

- the page already ships a production-optimized bundle and the issue is elsewhere, such as image weight, animation frequency, or server latency
- the code path is already minimal and the remaining payload is required for first render
- the proposed split is speculative and there is no evidence that the dependency is optional or non-critical
- the change would alter runtime behavior rather than only remove unused or development-only code

## Required validation

Each validation ID below is operational: it describes what must be true in the code or build output, and what evidence should be checked.

### `production_build_mode_enabled`

**Meaning:** The shipped client build is configured for production output rather than development output.

**Evidence from the packet:**
- `NODE_ENV=development webpack` changed to `NODE_ENV=production webpack`
- webpack `mode: "none"` changed to `mode: "production"`
- the build script was updated to run production mode

**What to verify:**
- the build command used for release artifacts sets production mode
- the bundler emits the production artifact, not a development artifact

### `development_scaffolding_removed_from_shipped_bundle`

**Meaning:** Development-only bundle scaffolding is removed from the shipped output.

**Evidence from the packet:**
- `devtool: "inline-source-map"` changed to `devtool: false`
- `chunkFormat: false` was removed
- React preset `development: true` was removed
- the build switched from development-oriented settings to production-oriented settings

**What to verify:**
- source-map or other development scaffolding is not emitted into the shipped client bundle when the evidence shows it was previously present
- debug-only preset behavior is not enabled in the production build

### `dead_code_elimination_enabled_in_bundler`

**Meaning:** Bundler optimizations that support pruning unused code are enabled.

**Evidence from the packet:**
- `minimize: false` changed to `minimize: true`
- `concatenateModules: false` changed to `true`
- `usedExports: false` changed to `true`
- `providedExports: false` changed to `true`
- `sideEffects: false` changed to `true`

**What to verify:**
- the bundler is configured to minify and analyze exports in production
- module concatenation and side-effect analysis are enabled where the evidence shows they were previously disabled

### `optional_large_dependency_isolated_or_removed_from_critical_bundle`

**Meaning:** A large optional dependency is either isolated into its own chunk or removed from the critical bundle.

**Evidence from the packet:**
- `SearchTrigger` was removed and replaced with `SearchBox` loaded with `client:idle`
- `unplugin-icons` was added with a comment stating that only the SVG paths actually used are bundled
- `manualChunks` isolates large dependencies such as `swagger-ui`, `arco-design`, `react-vendor`, `react-router`, `lightweight-charts`, `recharts`, `react-window`, `web-vitals`, `pdfmake`, and `d3-vendor`

**What to verify:**
- the dependency is not required for initial render, or
- the dependency is split into a separate chunk with a clear reason tied to size or optionality
- the change does not move required critical-path code out of the initial bundle

## Recommended approaches

Use production bundling settings first, then split only what is demonstrably optional or heavy.

### Good: production webpack settings

```js
module.exports = {
  mode: "production",
  devtool: false,
  optimization: {
    minimize: true,
    concatenateModules: true,
    usedExports: true,
    providedExports: true,
    sideEffects: true,
    splitChunks: false,
  },
};
```

**Why this is evidence-derived:** the supplied webpack patch moved from development-oriented settings to production-oriented settings and enabled the optimization flags above.

### Good: isolate large dependencies in Vite

```ts
export default defineConfig({
  build: {
    sourcemap: false,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('@arco-design/web-react')) return 'arco-design';
          if (id.includes('react-dom') || id === 'react') return 'react-vendor';
          if (id.includes('swagger-ui-react') || id.includes('swagger-ui')) return 'swagger-ui';
        },
      },
    },
  },
});
```

**Why this is evidence-derived:** the supplied Vite patch uses manual chunking to isolate large dependencies and production minification to reduce shipped JavaScript.

### Good: defer non-critical UI

```astro
<SearchBox
  lang={currentLang}
  placeholder={t('search.placeholder')}
  ariaLabel={t('search.ariaLabel')}
  client:idle
/>
```

**Why this is evidence-derived:** the header changed from a placeholder search trigger to an idle-loaded search component, reducing initial client work.

## Anti-patterns

The evidence packet does not justify a universal regex-based anti-pattern list for this strategy. Use the following operational rule instead:

- do not reintroduce development-only bundle output into production artifacts
- do not keep large optional dependencies in the critical path when they can be isolated or deferred
- do not assume every chunk split is beneficial without confirming that the split code is non-critical

## How to verify

Use before/after measurement on the same page and the same lab setup.

### Measure these signals

- Lighthouse JavaScript
- Lighthouse Total Blocking Time
- Lighthouse unused JavaScript

### Verification criteria

- the production build ships less JavaScript than the development-oriented build
- unused JavaScript decreases if dead-code elimination is working
- Total Blocking Time does not worsen after the bundle changes
- if a dependency was split out, confirm the initial bundle no longer includes that code path and that the split chunk is only loaded when needed

Do not assume a fixed improvement percentage. The evidence supports directionality, not a guaranteed magnitude.

## Evidence and confidence

### Observed facts

- In `yuuttana1223/web-speed-hackathon-2026#13`, the client build moved from development-oriented settings to production-oriented settings:
  - `NODE_ENV=development webpack` became `NODE_ENV=production webpack`
  - webpack `mode` became `production`
  - `devtool` became `false`
  - `minimize`, `concatenateModules`, `usedExports`, `providedExports`, and `sideEffects` were enabled
  - `SearchTrigger` was removed from the header and replaced with `SearchBox` loaded with `client:idle`
- In `expressjs/expressjs.com#2213`, `unplugin-icons` and `vite-plugin-svgr` were added, with an explicit comment that only used SVG paths are bundled for icons actually used.
- In `gxcsoccer/AlphaArena#516`, the codebase added manual chunking and production minification, including isolation of large dependencies into named chunks.

### Inference

- These changes are consistent with reducing shipped JavaScript and unused JavaScript, which is the mechanism behind the target CWV metrics.
- The evidence supports production bundling and selective chunk isolation, but not a universal rule that every chunk split is beneficial.

### Confidence

Medium. The direction is consistent across three repositories, but the measured deltas were not provided, so the playbook should remain conditional and verification-driven.

## Risks and limitations

- Chunk splitting can backfire if a dependency is split away from the critical path but still needed immediately.
- Production minification and export analysis can change runtime behavior if the codebase relies on side effects that were not modeled correctly.
- Removing development scaffolding is only safe when the shipped bundle does not depend on it.
- Isolating large libraries helps only when those libraries are truly optional or non-critical for initial render.
- The supplied evidence does not justify universal browser support claims, fixed percentage gains, or blanket recommendations to split every vendor package.