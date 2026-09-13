### Separate personalized state from cacheable page HTML (CS/AMS)

Do not render session- or user-specific data into otherwise public page HTML. A shared cache must serve the same representation to every anonymous visitor.

```html
<!-- Bad — apps/site/components/page/page.html -->
<sly data-sly-use.profile="com.site.core.models.ProfileModel" />

<div class="site-page">
  <p>Welcome, ${profile.displayName}</p>
  <sly data-sly-resource="${'content' @ resourceType='site/components/content/container'}" />
</div>
```

**Why this is bad:** The page response varies by authenticated user. Caching it can expose one visitor's name or account state to another visitor.

A client-side approach can render a shared page shell and load only the required authenticated state after the cacheable HTML is delivered.

```html
<!-- Good — apps/site/components/page/page.html -->
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html" />

<div class="site-page" data-profile-endpoint="/bin/site/profile">
  <sly data-sly-resource="${'content' @ resourceType='site/components/content/container'}" />
</div>

<sly data-sly-call="${clientlib.js @ categories='site.public-page'}" />
```

```javascript
// Good — apps/site/clientlibs/public-page/profile.js
document.addEventListener('DOMContentLoaded', async () => {
  const page = document.querySelector('.site-page');
  const endpoint = page?.dataset.profileEndpoint;

  if (!endpoint) {
    return;
  }

  const response = await fetch(endpoint, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    return;
  }

  const profile = await response.json();
  const greeting = document.querySelector('[data-profile-greeting]');

  if (greeting && profile.displayName) {
    greeting.textContent = `Welcome, ${profile.displayName}`;
  }
});
```

Keep client-sensitive pages such as account and checkout out of shared caching. Do not use this pattern in a way that shares protected user data through a cacheable page shell.

> **Source PRs** — **approach:** ls1intum/Artemis#5322, metabase/shoppy#71, nautobot/nautobot#7165, next-step/infra-subway-monitoring#595, shopware/frontends#309