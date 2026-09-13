### Remove confirmed-unused exports and modules

After confirming that an export or module has no consumers, delete it instead of relying only on tree shaking. One source PR reported that tree shaking did not remove all unused code and that removing unused functions produced an approximately 3 KB net bundle decrease.

```javascript
// Delete an unused export or module only after confirming it has no consumers.
```

Check relevant imports and usage before removing code, then run the applicable build, type checks, and functional tests after removal.

> **Source PRs** — **approach:** Jujulego/jill#1230, Automattic/wp-calypso#108174, OpenNews/srccon-site-starterkit#1, ngareleo/tvke#12, dailydotdev/apps#639 · **anti-pattern:** getsentry/sentry#83982, SolidInvoice/SolidInvoice#1551, konturio/disaster-ninja-fe#894, getsentry/sentry#83569