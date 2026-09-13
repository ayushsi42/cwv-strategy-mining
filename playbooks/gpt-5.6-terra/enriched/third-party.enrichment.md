### Client-side translation loaded after interactive

The LocalizeJS integration pulls localized strings after the page becomes interactive. The source evidence notes that users may see a flash of English before their preferred language is applied.

**Why this is bad:** Visitors may see the default language before their preferred language is applied. The LocalizeJS widget can remain in the DOM with `display: none` and include anchors without `href` attributes, which the PR identified as causing Lighthouse's crawlable-anchors SEO audit to fail.

> **Source PRs** — **approach:** gatsbyjs/gatsby#35403, adobecom/express#930, ResearchHub/researchhub-web#1410, cs-soc-tudublin/Plume#23, sourcegraph/about#5743 · **anti-pattern:** code-dot-org/code-dot-org#66358, mozilla/addons-frontend#12001, ant-design/ant-design#52300, newrelic/docs-website#3763