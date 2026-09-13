### Preload the marketing helper when page-modification features are needed

```js
// libs/utils/utils.js

async function checkForPageMods() {
  if (!(pzn || pznroc || target || promo || mepParam
    || mepHighlight || mepButton || mepParam === '' || xlg || ajo)) return;

  loadLink(`${getConfig().base}/martech/helpers.js`, {
    rel: 'preload',
    as: 'script',
    crossorigin: 'anonymous',
  });

  const promises = loadMepAddons();
  // Continue loading page-modification features.
}
```

**Why this approach is used:** The evidence PR preloads `martech/helpers.js` after detecting that page-modification features are relevant, then loads the MEP addons. The PR does not provide evidence that this preload improves or harms LCP.

> **Source PRs** — **approach:** Shopify/dawn#2258, Quansight/ragna#312, scandipwa/scandipwa#3139, phillipc0/WA-DP#113, cfpb/hmda-frontend#2180 · **anti-pattern:** adobecom/milo#4757