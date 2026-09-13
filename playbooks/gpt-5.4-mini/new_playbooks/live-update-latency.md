---
issue_type: live-update-latency
applicable_flavors:
- eds
- cs
- ams
- headless
risk_tier: medium
required_validation:
- live_subscription_source_confirmed
- update_path_is_client_rendered
- no_server_push_or_polling_fix
- scroll_behavior_understood
- state_deduplication_present
forbidden_techniques:
- pattern: \bsetInterval\s*\(
  reason: Don't poll for live updates on a timer — it adds latency, wastes CPU, and
    makes the UI feel less immediate than event-driven updates
- pattern: \bsetTimeout\s*\(\s*[^,]+,\s*(?:1[0-9]{3,}|[2-9][0-9]{3,})\s*\)
  reason: Don't use long fixed delays to 'wait' for live data — it hides latency instead
    of reducing it
- pattern: \bwindow\.location\.reload\s*\(
  reason: Don't reload the whole page to show new live data — it destroys interaction
    state and worsens INP
- pattern: \brouter\.reload\s*\(
  reason: Don't force a route reload for live updates — update the visible state in
    place instead
- pattern: \bscrollTo\s*\(\s*\{\s*top\s*:\s*0
  reason: Don't auto-jump the viewport to the top on every incoming event — preserve
    user scroll position unless the user is already anchored there
- pattern: \bscrollIntoView\s*\(
  reason: Don't force-scroll the page for each live event — it creates jank and can
    steal focus from the user's current interaction
source_prs:
- BenGWeeks/lightning-piggy-mobile#360
- apollographql/embeddable-explorer#224
- dannydeezy/nosft#84
- appwrite/sdk-generator#943
---
# Live update latency

> **Risk tier:** medium · **Applies to:** EDS, CS, AMS, Headless · **CWV metric:** INP

## What this addresses

This issue type covers client-side subscription flows that receive new data after the initial render and push it into visible UI state. Reducing the delay between the event arriving and the UI reflecting it can make interactions feel more immediate and improve INP by shortening the perceived wait after user actions or incoming live events.

## When to apply / when to skip
**Apply when:**
- The page already has a persistent client-side subscription, websocket, SSE, or pub/sub listener
- Incoming events are merged into visible state, lists, badges, threads, or cards on the client
- The current implementation waits for a refresh, focus event, or manual action before showing new data
- The update path can be changed without altering server contracts or auth flows

**Skip when:**
- The data is not live and only changes on full navigation or explicit refresh
- The bottleneck is server delivery, cache invalidation, or backend fanout rather than client rendering
- The UI must preserve a strict ordering or transactional boundary that cannot be safely updated incrementally
- The change would require redesigning the subscription protocol, not just the client update path
- The live update would auto-scroll or reflow content in a way that could disrupt the user's current interaction and needs product review first

## Recommended approaches

### Subscribe once, then commit incoming events directly into state

```js
export default function decorate(block) {
  const state = { items: [] };

  const render = () => {
    block.innerHTML = `
      <ul class="live-feed">
        ${state.items.map((item) => `<li data-id="${item.id}">${item.title}</li>`).join('')}
      </ul>
    `;
  };

  const unsubscribe = liveFeed.subscribe((event) => {
    if (state.items.some((item) => item.id === event.id)) return;
    state.items = [event, ...state.items];
    render();
  });

  block.addEventListener('unload', unsubscribe);
  render();
}
```

This removes the extra wait for a refresh cycle and makes the UI reflect the event as soon as it arrives. A small dedupe check prevents duplicate deliveries from causing repeated renders.

### Reconcile into the existing view model without remounting the screen

```html
<sly data-sly-use.model="com.example.core.models.LiveFeedModel" />
<div class="live-feed" data-live-feed>
  <ul data-live-feed-list>
    <sly data-sly-list.item="${model.items}">
      <li data-thread-id="${item.partnerPubkey}">
        <span class="thread-title">${item.title}</span>
        <span class="thread-unread">${item.unreadCount}</span>
      </li>
    </sly>
  </ul>
</div>
```

```js
(function () {
  function updateThreadRow(partnerPubkey) {
    var rows = document.querySelectorAll('[data-thread-id]');
    rows.forEach(function (row) {
      if (row.getAttribute('data-thread-id') === partnerPubkey) {
        var unread = row.querySelector('.thread-unread');
        if (unread) {
          unread.textContent = String(parseInt(unread.textContent, 10) + 1);
        }
        row.setAttribute('data-has-new-message', 'true');
      }
    });
  }

  subscribeDmMessages(function (partnerPubkey) {
    updateThreadRow(partnerPubkey);
  });
}());
```

Updating the current view model keeps focus, selection, and scroll position intact, which is important for INP. The browser only repaints the changed rows instead of tearing down and rebuilding the page.

### Preserve scroll position unless the user is already anchored to the live edge

```js
export default function decorate(block) {
  const list = block.querySelector('[data-live-feed-list]');
  const state = { isAtTop: true, latestEventId: null };

  const onScroll = function () {
    state.isAtTop = list.scrollTop <= 24;
  };

  list.addEventListener('scroll', onScroll);

  liveFeed.subscribe(function (event) {
    state.latestEventId = event.id;
    if (!state.isAtTop) return;

    const item = document.createElement('li');
    item.textContent = event.title;
    list.insertBefore(item, list.firstChild);
  });
}
```

This keeps live updates visible without hijacking the viewport during active reading or typing. The user gets immediacy when they are already following the live feed, but not when they are interacting elsewhere.

## Anti-patterns

### Refreshing the whole page or route for each event

```js
(function () {
  liveFeed.subscribe(function () {
    window.location.reload();
  });
}());
```

**Why this is bad:** A full reload destroys interaction state and turns a small live update into a heavy navigation, which can make the UI feel slower and hurt INP.

### Polling on a timer instead of reacting to the event

```js
(function () {
  var id = setInterval(function () {
    fetch('/api/live-items')
      .then(function (r) { return r.json(); })
      .then(function (next) {
        renderItems(next);
      });
  }, 5000);

  window.addEventListener('unload', function () {
    clearInterval(id);
  });
}());
```

**Why this is bad:** Timer polling adds avoidable delay between the event and the visible update, and it burns CPU even when nothing changes.

### Forcing the viewport to jump on every incoming item

```js
(function () {
  liveFeed.subscribe(function (latestEvent) {
    if (latestEvent) {
      var list = document.querySelector('[data-live-feed-list]');
      if (list) {
        list.scrollTop = 0;
      }
    }
  });
}());
```

**Why this is bad:** Auto-jumping the scroll position on every live event interrupts reading and interaction, creating jank and making the update feel less responsive.

### Delaying the UI with an arbitrary timeout before showing the event

```js
(function () {
  liveFeed.subscribe(function (event) {
    setTimeout(function () {
      prependLiveItem(event);
    }, 2000);
  });
}());
```

**Why this is bad:** A fixed delay hides the live event instead of reducing latency, so the user still waits even though the data has already arrived.

## When to apply / when to skip

### EDS

Use block-level client-side code to subscribe once and update the block's local state in place. If the live data is rendered inside a block, keep the subscription lifecycle inside `decorate(block)` and avoid remounting the block on every event.

```js
export default function decorate(block) {
  const state = { items: [] };

  const render = () => {
    block.innerHTML = `
      <ul class="live-feed">
        ${state.items.map((item) => `<li>${item.title}</li>`).join('')}
      </ul>
    `;
  };

  const unsubscribe = liveFeed.subscribe((event) => {
    if (state.items.some((item) => item.id === event.id)) return;
    state.items = [event, ...state.items];
    render();
  });

  block.addEventListener('unload', unsubscribe);
  render();
}
```

If the live feed is tied to a visible list, preserve the user's scroll position and only auto-scroll when the block is already anchored to the live edge.

### CS

Prefer updating the existing component state or Sling-backed model output rather than triggering a page refresh. If the live data is surfaced in a component, keep the client-side subscription in the component script and let the HTL markup remain stable.

```html
<!-- Good: stable component shell -->
<sly data-sly-use.model="com.example.core.models.LiveFeedModel" />
<div class="live-feed" data-live-feed>
  <ul data-live-feed-list>
    <sly data-sly-list.item="${model.items}">
      <li>${item.title}</li>
    </sly>
  </ul>
</div>
```

```js
// Good: client script updates the existing list in place
subscribeLiveFeed((event) => {
  appendOrPrependRow(event);
});
```

Avoid coupling live updates to a full page refresh or to a clientlib that remounts the entire component tree.

### AMS

Keep the live-update logic in the page's client-side script or component JS and avoid server-side redirects or reloads to surface new data. If the page uses JSP/HTL-like rendering, the live subscription should only patch the visible fragment that changed.

```jsp
<!-- Good: render a stable container and patch it from client JS -->
<div id="live-updates" class="live-updates">
  <c:forEach items="${model.items}" var="item">
    <div class="live-updates__row">${item.title}</div>
  </c:forEach>
</div>
```

```js
subscribeLiveFeed((event) => {
  updateLiveRow(event);
});
```

When the live feed is inside a scrollable panel, preserve the current scroll offset unless the user is already at the top or bottom and expects new content to appear there.

### Headless

In headless apps, the same rule applies: subscribe once, dedupe incoming events, and update the visible state without remounting the route or resetting the list. The fix belongs in the client rendering layer, not in the API contract.

```tsx
useEffect(() => {
  const unsubscribe = socket.on('message', (event) => {
    setMessages((current) => mergeLiveEvent(current, event));
  });

  return unsubscribe;
}, []);
```

If the UI is virtualized, ensure the live insert path does not invalidate the whole window on each event; patch only the affected rows.