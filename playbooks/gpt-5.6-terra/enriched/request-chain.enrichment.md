### Parallelize independent lazy module imports

When lazy-loaded modules are independent, consider loading them in parallel. The evidence identifies parallelizing lazy loading for required dependencies as a way to keep bundle size as small as possible.

```javascript
// Sequential loading
export default async function decorate(block) {
  const mapModule = await import('./map.js');
  const filtersModule = await import('./filters.js');

  const map = mapModule.createMap(block.querySelector('.map'));
  filtersModule.attachFilters(block.querySelector('.filters'), map);
}
```

**Why this is bad:** The evidence flags sequential independent work as an opportunity for parallelization.

```javascript
// Parallel loading
export default async function decorate(block) {
  const [mapModule, filtersModule] = await Promise.all([
    import('./map.js'),
    import('./filters.js'),
  ]);

  const map = mapModule.createMap(block.querySelector('.map'));
  filtersModule.attachFilters(block.querySelector('.filters'), map);
}
```

Only apply this pattern when the modules are independent.

> **Source PRs** — **approach:** scalableminds/webknossos#5993, konturio/disaster-ninja-fe#344, decentraland/js-sdk-toolchain#549, digitalfabrik/integreat-app#942, elastic/kibana#161144 · **anti-pattern:** platform-q-ai/jarga-admin#79, vorausrobotik/vdoc#128