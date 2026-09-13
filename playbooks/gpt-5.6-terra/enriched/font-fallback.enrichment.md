### Fix 4: Import only the font character sets your site needs

**Anti-pattern: Shipping a full multi-script font file when the site only needs a subset of its characters**

**Why this is bad:** loading character sets that are not needed can increase font bundle size.

**Approach:** Import only the character sets needed by the site. For example, a Latin-only site can use a Latin character subset rather than a font file containing additional scripts.

**Precondition:** confirm which languages and character sets the site needs before limiting font imports.

**Why this helps:** importing only needed characters can reduce font bundle size.

> **Source PRs** — **approach:** mumendiraneyya/clinic_website#23, UMAprotocol/website#128, gnolang/www.gno.land#9, lsst-epo/rubin-obs-client#560, codeit-fe16-part4-team1/project-mogazoa-app#84 · **anti-pattern:** lifeisbeautifu1/modern-react-app#61