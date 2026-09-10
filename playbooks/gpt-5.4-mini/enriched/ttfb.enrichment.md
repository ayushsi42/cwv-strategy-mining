### Normalize trailing-slash API routes to avoid redirect-driven duplicate requests

When an API is sensitive to trailing slashes, calling the non-canonical path can trigger a redirect and cause the same logical request to be issued twice. Use the canonical slash-terminated route directly so the client does not pay the extra round trip.

```js
// Good — call the canonical route directly
axios.get(`${this._apiBaseUrl}/projecttags/`, {
  headers: await getAuthorizationHeaders(this._getAccessToken),
})

axios.get(`${this._apiBaseUrl}/profiles/`, {
  headers: await getAuthorizationHeaders(this._getAccessToken),
  params: { email },
})

axios.get(`${this._apiBaseUrl}/projects/${projectId}/${sampleUnitMethod}/${id}/`, {
  headers: await getAuthorizationHeaders(this._getAccessToken),
})
```

> **Source PRs** — **approach:** ogabasseyy/Baci#2479, data-mermaid/mermaid-webapp#891