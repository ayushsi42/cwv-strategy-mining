### Remove a confirmed-unused library or feature module

When a dependency or feature is no longer used anywhere, remove the import, entry point, and implementation together. For AEM, also remove any clientlib references or block JS that still pull the code into the page.

```javascript
// Before
import moment from 'moment';
import 'moment-timezone';

export function formatDate(value) {
  return moment(value).format('YYYY-MM-DD');
}

// After
export function formatDate(value) {
  return new Date(value).toISOString().slice(0, 10);
}
```

If the feature is retired entirely, delete the component or module and remove the last root-level reference so it cannot be bundled through a lingering include.

## Anti-patterns

### Replacing code without removing the old import path

```javascript
// Bad
import moment from 'moment';
import dayjs from '@utils/dayjs';

export function formatDate(value) {
  return dayjs(value).format('YYYY-MM-DD');
}
```

**Why this is bad:** The old package is still imported, so the unused bytes remain in the bundle and the page still pays the parse cost. If the goal is to reduce shipped code, remove the obsolete import and any transitive references.

### Deleting a feature from one page while leaving a shared include in place

```javascript
// Bad
export function Page() {
  return (
    <>
      <MainContent />
      {/* removed here, but still imported in shared shell */}
    </>
  );
}
```

**Why this is bad:** The feature may still be pulled into other pages through a shared shell, clientlib, or block entry point. Removing only one usage does not guarantee the code is globally unused.