### Public asset compression by default

```ts
// Nitro / build output config
export default defineNitroConfig({
  compressPublicAssets: true,
})
```

This enables `.gz` and `.br` variants for generated public assets by default, matching `1.x` behavior.

> **Source PRs** — **approach:** next-step/infra-subway-monitoring#595, Princeton-CDH/lenape-timetree#23, Hackreactor-Quantum-of-Solace/Project-Atelier#59, solidjs/solid-start#2112