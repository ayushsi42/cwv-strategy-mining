### Keep small, page-specific inline styles in place

If the inline CSS is genuinely unique to the page or component and only covers a tiny amount of layout or spacing, keep it inline rather than moving it into a global stylesheet.

**Good example:**
```html
<div class="login-message" style="margin-top: 1rem; text-align: center;">
  To connect your Patreon account, log in with Twitch first.
</div>
```

This is the right tradeoff when the alternative would be adding a stylesheet just to carry one or two page-specific rules.

> **Source PRs** — **approach:** spryker/oryx#331, therungg/therun-frontend#95, microsoft/griffel#139, microsoft/griffel#135, ita-social-projects/Forum#363 · **anti-pattern:** ant-design/ant-design#53954, ant-design/ant-design#51843, ant-design/ant-design#51897