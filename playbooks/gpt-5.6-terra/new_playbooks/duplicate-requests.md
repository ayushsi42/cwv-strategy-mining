---
issue_type: duplicate-requests
risk_tier: medium
applicable_flavors:
- eds
- cs
- ams
- headless
forbidden_techniques: []
required_validation: []
source_prs:
- getsentry/sentry#84763
- getsentry/sentry#83690
- getsentry/sentry#83884
- rayanfer32/nexus-explorer-next#30
- elastic/kibana#133371
---
# Duplicate requests

## What this addresses

The evidence shows migrations from promise- or legacy async-component-based data loading to React Query:

- Kibana refactors Cases connector and action-license hooks to use React Query. The selector modal is wrapped in a `QueryClientProvider`.
- Sentry replaces a single bootstrap promise for organization, projects, and teams with React Query queries. The PR describes this as a step toward client-side caching of projects.
- Sentry converts legacy async components to query hooks while preserving loading, error, and empty-state handling.
- A Sentry service-hooks mutation updates the matching cached query data after a successful response.

## When to apply / when to skip
**Apply when:**
- Existing request loading is being migrated to query-based state management
- The response can be represented by a query key and reused according to an explicit freshness policy
- Loading, error, and empty states remain handled after the migration
- Successful mutations update or otherwise refresh the corresponding query state

## Recommended approaches

### Use query hooks for shared request state

The Kibana and Sentry changes replace direct or legacy asynchronous loading patterns with React Query-based hooks. Query hooks can centralize loading and error state for consumers that share the same query client.

### Define freshness deliberately

Sentry’s bootstrap queries define a stale-time policy; the source comments describe stale time as determining whether a query should be refetched. Choose a freshness policy appropriate to the resource rather than relying on an unspecified default.

### Preserve loading, error, and empty states

The Sentry service-hooks conversion explicitly renders:

- `LoadingIndicator` while the query is pending
- `LoadingError` with retry support when the query fails
- An empty message when no service hooks are returned

Retain equivalent states when converting existing request paths.

### Update cached data after successful mutations

The Sentry service-hooks mutation updates the cached service-hook list after a successful `PUT` response:

```typescript
setApiQueryData<ServiceHook[]>(
  queryClient,
  [`/projects/${organization.slug}/${projectId}/hooks/`],
  oldHookList => {
    return oldHookList.map(h => {
      if (h.id === data.id) {
        return {
          ...h,
          ...data,
        };
      }
      return h;
    });
  }
);
```

Use the successful server response when it represents the cached resource. Otherwise, refresh or invalidate the affected query state.

## Anti-patterns

### Using `staleTime: 0` without an intentional refetch policy

```typescript
useApiQuery<ServiceHook[]>(['/projects/.../hooks/'], {
  staleTime: 0,
});
```

**Why this needs review:** The Sentry source defines stale time as the setting that determines whether a query should be refetched. A `staleTime: 0` configuration should therefore be intentional and compatible with the desired request behavior.

### Dropping state handling during a query migration

**Why this needs review:** The Sentry conversions retain pending, error, retry, and empty-state behavior. A migration that removes those states changes the user-visible behavior even if the request itself succeeds.

### Leaving cached query data unchanged after a successful write

**Why this needs review:** The Sentry service-hooks mutation updates cached query data after a successful response. If an edit path does not update, invalidate, or refetch the affected data, later consumers may continue to read older query state.