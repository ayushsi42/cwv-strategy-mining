### Variable font instead of separate static weights

```css
/* Good */
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter-variable.woff2') format('woff2');
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}

body {
  font-family: 'Inter', system-ui, sans-serif;
}
```

Variable fonts can replace multiple static weight files with a single WOFF2, which can reduce font requests and total payload. This can be especially useful when the design uses several weights across headings and body text.

> **Source PRs** — **approach:** CareerCatalyst/Career-Catalyst#4, earlman/me-dev#15, allcll/allcll-frontend#334, actualbudget/actual#444, okta/okta-signin-widget#3956