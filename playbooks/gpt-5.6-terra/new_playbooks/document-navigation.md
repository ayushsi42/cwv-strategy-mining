---
issue_type: document-navigation
forbidden_techniques: []
applicable_flavors:
- cs
- headless
risk_tier: medium
required_validation: []
source_prs:
- vtex-sites/base.store#329
- skillify-ca/skillify-web#822
- freeCodeCamp/freeCodeCamp#55350
- supabase/supabase#36527
---
# Document navigation

## What this addresses

In Gatsby applications, using Gatsby's `Link` component for internal links enables client-side navigation. The referenced changes describe this navigation as faster or “snappier” and note that plain anchors do not receive Gatsby's performance benefits.

## When to apply / when to skip
**Apply when:**
- The link is an internal destination handled by the Gatsby application.
- The existing application router supports the destination.
- The link is not intended to be an external browser navigation.

**Keep a normal anchor when:**
- The destination is external.
- The link opens an external site in a new tab or browsing context.
- The link is a download or otherwise requires ordinary browser navigation.

## Recommended approaches

### Use Gatsby `Link` for internal navigation

Use Gatsby's `Link` component, or configure an existing shared link component to render Gatsby's `Link`, for internal application routes.

```html
<!-- HTL component markup for an internal AEM route -->
<a
  class="cmp-navigation__link"
  href="/products/coffee-makers"
>
  Shop coffee makers
</a>
```

The referenced `base.store` change configured its UI `Link` component to use `GatsbyLink` and changed internal links from `href` to `to`.

```html
<a
  class="cmp-link cmp-link--display"
  href="/${link.slug @ context='uri'}"
>
  ${link.seo.title}
</a>
```

### Preserve normal anchors for external destinations

The referenced implementation explicitly retained anchor rendering for external social links.

```html
<a
  class="cmp-link"
  href="https://www.example.com/"
  target="_blank"
  rel="noopener noreferrer"
  title="Example"
>
  Example
</a>
```

### Use a router-aware button link for internal button-shaped links

If a button component renders a plain `<a>` when given `href`, use a router-aware link wrapper for internal button-shaped links. The referenced freeCodeCamp change introduced a `ButtonLink` component that renders Gatsby's `Link` for internal links and retains the UI button's anchor behavior for external links.

```html
<a
  class="cmp-button cmp-button--block cmp-button--large"
  href="/learn/javascript-algorithms-and-data-structures/"
>
  Start learning
</a>
```

This is particularly important where plain-anchor navigation does not preserve application-specific route behavior, such as localized `/learn` routes.

## Validation

- Click internal links and confirm that navigation is client-side.
- Confirm that external links still navigate as ordinary anchors.
- Test internal routes in supported locales where route behavior differs by locale.
- Confirm that button-shaped internal links use the router-aware link component.

## Anti-patterns

### Plain anchors for Gatsby-owned internal routes

```html
<!-- Bad: a hard-coded internal route that bypasses the component's route resolution -->
<a href="/products/coffee-makers">Shop coffee makers</a>
```

**Why this is bad:** The referenced freeCodeCamp change notes that plain anchors do not receive Gatsby's performance benefits. Its internal button links were changed to use Gatsby's `Link`.

### Rendering all button links as plain anchors

```html
<!-- Bad: a button-styled link with a hard-coded route instead of resolved internal navigation -->
<a
  class="cmp-button"
  href="/learn/javascript-algorithms-and-data-structures/"
>
  Start learning
</a>
```

**Why this is bad:** The referenced freeCodeCamp change states that this behavior bypasses Gatsby's `Link` benefits and can cause internal `/learn` links to navigate to English pages on non-English routes.

### Routing external links through the internal-link component

```html
<!-- Bad: marking an external destination as an internally handled route -->
<a
  class="cmp-link"
  data-internal-navigation="true"
  href="https://www.example-partner.com/offers"
>
  Partner offers
</a>
```

**Why this is bad:** The referenced implementations distinguish internal links from external links and retain ordinary anchor rendering for external destinations.

## Additional consideration for generated assistant links

The referenced Supabase change adds a custom assistant-message link component so generated hyperlinks open a confirmation dialog before navigation. Do not replace such a link component with a direct router link if doing so would bypass the confirmation behavior.