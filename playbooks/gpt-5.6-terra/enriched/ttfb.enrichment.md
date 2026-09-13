### Keep session-aware routes out of shared caches

Do not shared-cache pages whose rendered HTML uses session context. Keep client-sensitive pages such as checkout and account pages client-rendered, and avoid rendering session data on the server when shared edge caching is enabled.

**Why this is bad:** If session-aware HTML is stored in a shared cache, it can be served to another user. The `useUserContextInSSR` setting should be used carefully with edge caching to avoid sharing user data.

Ensure that public-page responses do not include session-specific data before enabling shared caching.

### Use long browser TTLs for content-hashed public DAM assets

Public DAM assets whose URLs include a content hash can use a long browser cache lifetime because an updated asset receives a new URL. In the cited implementation, browsers cache public DAM files and images for one year, while proxies and CDNs cache them for one day.

```http
Cache-Control: max-age=31536000, s-maxage=86400, public
```

**Why this is bad:** A long cache duration can cause users to continue receiving an older asset when the URL does not change after an update.

Verify that an asset URL changes when its content changes before applying a one-year browser TTL.

> **Source PRs** — **approach:** shopware/frontends#309, colonial-heritage/colonial-collections#108, vivid-planet/comet#3926