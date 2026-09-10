---
issue_type: duplicate-requests
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation: []
forbidden_techniques: []
source_prs:
- adobecom/express#998
- ITISFoundation/osparc-simcore#7487
- bitwarden/clients#14740
- adobe/adobe-design-website#81
---
# Duplicate requests

> **Risk tier:** medium · **Applies to:** EDS, Headless · **CWV metric:** LCP

## What this addresses

Multiple components can request the same resource concurrently before the first response completes. Sharing an in-flight Promise can avoid duplicate network requests. In the Express PR, deduplicating requests, including `placeholders.json`, was intended to save bandwidth and was associated with a measured 0.1–0.2 second LCP improvement in local testing.

## When to apply / when to skip
**Apply when:**
- A network waterfall shows two or more concurrent requests for the same resource.
- Concurrent callers can use the same response.
- The request is safe to share for the relevant page, user, and response context.

**Skip when:**
- Callers require different responses or request behavior.
- The duplicate requests are sequential rather than concurrent; an in-flight Promise cache will not reduce them.

## Recommended approaches

### Share only the in-flight JSON request

Use a shared Promise for a request that is already in progress. Store the Promise before awaiting it, return it to concurrent callers, and clear it after completion so a later request can run.

```javascript
// Good: scripts/shared-request.js
const inFlightRequests = new Map();

export function getSharedJson(requestKey, url, options = {}) {
  const existingRequest = inFlightRequests.get(requestKey);
  if (existingRequest) return existingRequest;

  const request = fetch(url, options)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status} ${url}`);
      }

      return response.json();
    });

  inFlightRequests.set(requestKey, request);

  return request.finally(() => {
    if (inFlightRequests.get(requestKey) === request) {
      inFlightRequests.delete(requestKey);
    }
  });
}
```

An in-flight cache deduplicates overlapping requests. Clearing the entry after completion allows a later caller to make a new request.

### EDS: use one shared request from block decoration

Import a shared helper from project scripts and use the same request key for callers that should share a response.

```javascript
// Good: blocks/article-list/article-list.js
import { getSharedJson } from '../../scripts/shared-request.js';

export default function decorate(block) {
  const locale = document.documentElement.lang || 'en';
  const endpoint = `/articles/query-index.json?locale=${encodeURIComponent(locale)}`;
  const requestKey = `articles:${locale}`;

  return getSharedJson(requestKey, endpoint).then((data) => {
    const list = document.createElement('ul');

    data.data.forEach((article) => {
      const item = document.createElement('li');
      const link = document.createElement('a');

      link.href = article.path;
      link.textContent = article.title;
      item.append(link);
      list.append(item);
    });

    block.replaceChildren(list);
  });
}
```

If an article-list block and a filter block decorate at the same time and use this helper with the same key, they receive the same in-flight request.

## Anti-patterns

### Fetching the same resource independently in each caller

```javascript
// Bad: blocks/filter-group/filter-group.js
export default async function decorate(block) {
  const response = await fetch('/ideas/query-index.json');
  const articles = await response.json();

  block.dataset.articleCount = String(articles.data.length);
}

// Bad: blocks/ideas-list/ideas-list.js
export default async function decorate(block) {
  const response = await fetch('/ideas/query-index.json');
  const articles = await response.json();
  const list = document.createElement('ul');

  articles.data.forEach((article) => {
    const item = document.createElement('li');
    item.textContent = article.title;
    list.append(item);
  });

  block.replaceChildren(list);
}
```

**Why this is bad:** Concurrent component decoration can produce duplicate requests for the same data. The referenced PRs use shared caches or in-flight Promises to avoid repeated requests.

### Caching a rejected Promise forever

```javascript
// Bad: a transient failure makes every later caller fail without retrying
let placeholdersRequest;

export function getPlaceholders() {
  if (!placeholdersRequest) {
    placeholdersRequest = fetch('/placeholders.json')
      .then((response) => response.json());
  }

  return placeholdersRequest;
}
```

**Why this is bad:** If the stored Promise rejects and is not cleared, later callers receive that same rejected Promise instead of starting another request.

## Flavor-specific notes

### EDS

The Express PR deduplicated placeholder requests by storing a shared Promise. Public resources such as placeholders, query indexes, and shared metadata can be candidates for this pattern when concurrent callers can use the same response.

### Headless

Apply the pattern in a shared data-access service rather than separately in each component. The Bitwarden PR stored in-flight token-refresh and sync Promises and returned the existing Promise when another sync request was already in progress.