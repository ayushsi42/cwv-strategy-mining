### Reserve a stable placeholder for icon/text swaps

When a control’s affordance changes after data arrives — for example, replacing an icon-only action with a text link, or swapping “Follow”/“Unfollow” labels in place — reserve the final control box up front so the label change doesn’t push adjacent content.

```html
<!-- Good — the action area keeps a stable footprint while the label changes -->
<div class="attachment-action">
  <a class="attachment-action__link" href="/downloads/report.pdf">Download</a>
  <span class="attachment-action__timestamp">Updated 2 hours ago</span>
</div>
```

```css
.attachment-action {
  min-height: 35px; /* reserve the final control height */
  display: flex;
  align-items: center;
  gap: 8px;
}
```

### Reserve height for lazy-loaded cards and charts

If a card, chart, map, or similar module renders a loading state first and then expands when data arrives, give the wrapper a real `min-height` that matches the loaded component so the page doesn’t jump when the content hydrates.

```html
<!-- Good — loading shell and loaded content share the same reserved height -->
<div class="chart-card">
  <div class="chart-card__skeleton" aria-hidden="true"></div>
  <div class="chart-card__content" hidden>
    <!-- loaded content -->
  </div>
</div>
```

```css
.chart-card {
  min-height: 139px;
}

.chart-card__skeleton {
  min-height: 139px;
}
```

> **Source PRs** — **approach:** keybase/client#25445, mozilla/bedrock#16009, guardian/dotcom-rendering#8570, SatcherInstitute/health-equity-tracker#1264, vtex-sites/base.store#300