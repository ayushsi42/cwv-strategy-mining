---
issue_type: date-formatting
applicable_flavors:
- cs
- ams
- headless
risk_tier: low
required_validation:
- localized_date_helper_identified
- date_display_is_client_side_only
- no_server_rendering_or_head_edit_required
- no_existing_locale_specific_formatter_in_path
forbidden_techniques: []
source_prs:
- dtpstat/website#1
- openmsupply/openmsupply-client#1151
- Automattic/wp-calypso#71580
- cockroachdb/cockroach#99848
- lightdash/lightdash#9323
- City-of-Helsinki/kukkuu-ui#640
- Expensify/App#64561
---
# Date formatting

> **Risk tier:** low · **Applies to:** CS, AMS, Headless · **CWV metric:** INP, UX responsiveness

## What this addresses

Localized date-format helpers change how timestamps, chart labels, and comment/activity UIs are rendered in the browser. The goal is to improve perceived responsiveness and interaction clarity by showing dates in the user's locale or timezone without changing loading behavior.

## When to apply / when to skip

**Apply when:**
- A UI is formatting timestamps, chart axes, comment metadata, or activity feeds on the client
- The current implementation uses a hard-coded format string or a single locale for all users
- The change can be made in a shared date utility or component without server-side rendering changes

**Skip when:**
- The issue is about data fetching, hydration, or initial page load rather than display formatting
- The date is already rendered correctly by an existing locale-aware helper
- The fix would require head edits, template rewiring, or server-side output changes
- The UI is headless-only and the date is rendered outside the browser client path

## Recommended approaches

### Centralize formatting in a shared client-side helper

Use one utility that maps the active locale to a formatter and keep all date display calls routed through it.

```ts
// Good: shared helper used by charts, tables, and comment UIs
export function formatDisplayDate(value, locale) {
  const date = typeof value === 'string' ? new Date(value) : value;
  const localeMap = {
    'en-GB': 'en-GB',
    'en-US': 'en-US',
    fr: 'fr-FR',
  };

  return new Intl.DateTimeFormat(localeMap[locale] || 'en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}
```

This keeps formatting behavior consistent across the UI and makes it easy to add more locales later without touching every component.

### Recompute the formatter only when the language actually changes

If the formatter must react to language changes, cache the `Intl.DateTimeFormat` instance keyed by locale instead of constructing one on every call, and listen for the app's language-change signal to invalidate the cache.

```js
// Good: locale-keyed formatter cache, updates when language changes
import { getCurrentLanguage, onLanguageChange } from '../intl/context.js';

const formatterCache = new Map();

function resolveLocale(language) {
  return language === 'en-GB' ? 'en-GB' : 'en-US';
}

function getFormatter() {
  const locale = resolveLocale(getCurrentLanguage());
  if (!formatterCache.has(locale)) {
    formatterCache.set(locale, new Intl.DateTimeFormat(locale, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }));
  }
  return formatterCache.get(locale);
}

// Drop any cached formatter for a locale that's no longer current so a
// stale instance is never reused across a language switch.
onLanguageChange(() => formatterCache.clear());

export function localisedDate(value) {
  return getFormatter().format(typeof value === 'string' ? new Date(value) : value);
}
```

This works well for interactive UIs where the user can switch language without a full reload.

### Keep chart labels and comment timestamps on the same formatter path

```ts
// Good: one formatter for both chart labels and comment timestamps
export function renderDateLabels(point, comment, locale) {
  const formatDate = (value) =>
    new Intl.DateTimeFormat(locale, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(typeof value === 'string' ? new Date(value) : value);

  return {
    chartLabel: formatDate(point.timestamp),
    commentMeta: formatDate(comment.createdAt),
  };
}
```

Using the same helper avoids mismatched date styles between adjacent UI elements, which improves clarity and reduces visual friction.

## Anti-patterns

### Hard-coding a single locale for every user

```ts
// Bad
export function formatDisplayDate(value) {
  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}
```

**Why this is bad:** It ignores the user's language and can make localized UIs feel inconsistent or incorrect, especially in charts and comment feeds.

### Replacing a shared helper with ad hoc `Intl.DateTimeFormat` calls in components

```ts
// Bad
export function CommentRow({ createdAt }) {
  return `<span>${new Intl.DateTimeFormat(navigator.language).format(new Date(createdAt))}</span>`;
}
```

**Why this is bad:** Scattering formatter logic across components makes behavior drift over time and makes language updates harder to manage consistently.

### Using a date formatter that does not react to language changes

```ts
// Bad
const formatter = (value) => new Date(value).toLocaleDateString();

export function ActivityItem({ timestamp }) {
  return formatter(timestamp);
}
```

**Why this is bad:** The output is tied to ambient browser defaults and may not update when the app's language context changes, which can be confusing in interactive UIs.

### Introducing a heavy timezone/date library for simple display formatting

```ts
// Bad
export function formatDisplayDate(value) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}
```

**Why this is bad:** It can add significant bundle weight for a simple display concern. In the evidence, adding `moment-timezone` was flagged as adding about 950KB to the cluster-ui bundle.

## Flavor-specific notes

### CS

Prefer a shared client-side utility or hook in the app's common UI layer, then update chart/comment components to call it. If the app already has an i18n context, wire the formatter to that context so language changes propagate naturally.

### AMS

Keep the change in the browser-rendered component path rather than JSP/server output. If multiple pages share the same timestamp component, update the shared helper instead of duplicating formatting logic in each view.

### Headless

Use the existing client app locale state as the source of truth. Avoid server-side assumptions about locale formatting unless the headless client already exposes a language context that can drive the formatter.