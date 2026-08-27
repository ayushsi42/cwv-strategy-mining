### Public asset compression by default

```ts
// Nitro / build output config
export default defineNitroConfig({
  compressPublicAssets: true,
})
```

This enables `.gz` and `.br` variants for generated public assets by default, matching `1.x` behavior.