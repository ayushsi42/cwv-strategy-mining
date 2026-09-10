---
issue_type: locale-bloat
applicable_flavors:
- eds
- cs
- headless
risk_tier: medium
forbidden_techniques: []
required_validation: []
source_prs:
- martincostello/apple-fitness-workout-mapper#635
- martincostello/costellobot#444
- martincostello/dependabot-helper#478
- martincostello/website#1321
---
# Locale bloat

## What this addresses

The evidence includes a webpack configuration that applies `ContextReplacementPlugin` to Moment's locale context and configures it with an `en-gb` locale pattern.

## Evidence-backed approach

In the documented webpack configuration, Moment locale handling is configured as follows:

```javascript
const webpack = require('webpack');

module.exports = {
  plugins: [
    new webpack.ContextReplacementPlugin(/moment[/\\]locale$/, /en-gb/),
  ],
};
```

This configuration was added alongside a migration from gulp to webpack and npm scripts.