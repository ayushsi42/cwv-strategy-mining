### Normalize API URLs to avoid redirect-induced duplicate requests

When an API is sensitive to trailing slashes, call the canonical URL directly so the client does not trigger an extra redirect and repeat the request.

```js
// Good — request the canonical endpoint directly
fetch(`${this._apiBaseUrl}/projecttags/`, {
  headers: await getAuthorizationHeaders(this._getAccessToken),
})

fetch(`${this._apiBaseUrl}/profiles/`, {
  headers: await getAuthorizationHeaders(this._getAccessToken),
})

fetch(
  `${this._apiBaseUrl}/projects/${projectId}/${sampleUnitMethod}/${id}/`,
  {
    headers: await getAuthorizationHeaders(this._getAccessToken),
  },
)
```

This avoids the `.../projecttags` → redirect → `.../projecttags/` pattern that can add extra network round trips and duplicate calls.

### Remove unused state from initialization dependencies

If a hook or initializer does not use a piece of state, remove it from the dependency list so it does not retrigger initialization unnecessarily.

```js
function App({ dexieCurrentUserInstance }) {
  const { isOfflineStorageHydrated, syncErrors } = useSyncStatus()

  useInitializeCurrentUser({
    dexieCurrentUserInstance,
    isMermaidAuthenticated,
    isAppOnline,
    handleHttpResponseErrorWithLogoutAndSetServerNotReachableApplied,
  })
}
```

```js
export const useInitializeCurrentUser = ({
  dexieCurrentUserInstance,
  isMermaidAuthenticated,
  isAppOnline,
  handleHttpResponseErrorWithLogoutAndSetServerNotReachableApplied,
}) => {
  // ...
}
```

This removes an unused dependency from the initialization flow.

> **Source PRs** — **approach:** data-mermaid/mermaid-webapp#891, Automattic/wp-calypso#97958