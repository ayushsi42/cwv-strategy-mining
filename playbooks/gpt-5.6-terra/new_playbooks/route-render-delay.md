---
issue_type: route-render-delay
required_validation: []
forbidden_techniques:
- pattern: \b(?:React\.)?lazy\s*\(\s*\(\s*\)\s*=>\s*import\s*\(
  reason: Do not lazy-load a route without establishing that it is non-critical; source
    PRs identify lazy-loaded modules as a source of additional JavaScript request
    waterfalls.
- pattern: \bgetAsyncLifecycle\s*\(\s*\(\s*\)\s*=>\s*import\s*\(
  reason: Do not make a primary application lifecycle asynchronous by default; source
    PRs changed primary lifecycles to synchronous loading and reported fewer JavaScript
    requests and snappier primary navigation.
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: high
source_prs:
- codecov/gazebo#3738
- Collaborative-Learning-Platform/frontend-app#23
- cozy/mespapiers#173
- coder/coder#4156
- zooniverse/front-end-monorepo#4371
- beyondessential/tupaia#4929
- openmrs/openmrs-esm-core#806
- chaibuilder/sdk#17
- cowprotocol/cowswap#4950
- redwoodjs/reloaded#20
- grafana/plugin-tools#1538
---
# Route render delay

## What this addresses

A client-rendered route may wait for an additional JavaScript module request before its content can render. Source PRs removed lazy loading from primary application components and lifecycles to reduce JavaScript requests and request waterfalls, with reports of snappier navigation.

This is a recommendation-only issue: making code synchronous can increase the bundle delivered at startup, and one source PR reported no bundle-size difference from lazy loading in its case. Evaluate the route and its bundle impact before changing its loading strategy.

## When to apply / when to skip
**Apply when:**
- The affected route is a default landing route or a primary-navigation destination.
- Evidence shows that an additional route-module request is delaying the route's primary content.
- The route can be made synchronous without adding unrelated or rarely used route code to the startup path.

**Skip when:**
- The route is rarely used or intentionally optional.
- The route-module request is not the relevant bottleneck.
- The proposed change makes all route modules synchronous rather than addressing the affected route.

## Recommended approaches

### Keep primary route code synchronous

For a route shell, statically include the code needed to render the default or primary-navigation destination. Keep optional functionality behind an intentional boundary.

```javascript
// blocks/app-shell/app-shell.js
import { decoratePrimaryNavigation } from './primary-navigation.js';
import { decorateLandingRoute } from './routes/landing.js';

export default function decorate(block) {
  decoratePrimaryNavigation(block);
  decorateLandingRoute(block);
}
```

A static import avoids an additional route-module request for the landing route. The decision should be limited to routes shown to be important to the initial or primary navigation experience.

### Keep optional route code deferred

```javascript
// ui.frontend/src/routes/register-routes.js
import { renderLandingRoute } from './landing-route.js';
import { renderProductRoute } from './product-route.js';

export function registerRoutes(app) {
  app.register('/home', renderLandingRoute);
  app.register('/products/:slug', renderProductRoute);

  app.registerDeferred('/admin', async () => {
    const { renderAdminRoute } = await import('./admin-route.js');
    return renderAdminRoute;
  });
}
```

This keeps the landing and product routes available without a separate route-module request while retaining a separate loading boundary for an optional administrative route.

## Anti-patterns

### Lazy-loading the route that owns initial content

```javascript
// Bad: the route waits for its module request before it can render.
export default function decorate(block) {
  import('./routes/landing.js').then(({ decorateLandingRoute }) => {
    decorateLandingRoute(block);
  });
}
```

**Why this is bad:** when the landing route is important to the initial experience, this adds a JavaScript request that can contribute to the request waterfalls identified in the source PRs.

### Making all routes synchronous because one route has a waterfall

```javascript
// Bad: all route modules are pulled into the startup module.
import { renderLandingRoute } from './landing-route.js';
import { renderProductRoute } from './product-route.js';
import { renderAdminRoute } from './admin-route.js';
import { renderAnalyticsRoute } from './analytics-route.js';
import { renderVisualEditorRoute } from './visual-editor-route.js';

export function registerRoutes(app) {
  app.register('/home', renderLandingRoute);
  app.register('/products/:slug', renderProductRoute);
  app.register('/admin', renderAdminRoute);
  app.register('/analytics', renderAnalyticsRoute);
  app.register('/editor', renderVisualEditorRoute);
}
```

**Why this is bad:** source PRs distinguish primary pages from routes that are not used on first load or are rarely used. Making every route synchronous can add code to the startup bundle without helping the affected route.