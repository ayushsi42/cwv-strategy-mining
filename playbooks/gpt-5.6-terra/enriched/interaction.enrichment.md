### Defer document-wide state changes until after the drawer starts painting

When runtime attribution identifies a slow navigation-drawer interaction, check whether the interaction synchronously updates large page regions—for example, by applying `inert` to `main` and `footer`. Start the visual drawer transition first, then defer the document-wide state update until a later frame.

#### Anti-pattern: update the entire page before the drawer can paint

```text
# EDS: blocks/navigation/navigation.js
export default function decorate(block) {
  const toggle = block.querySelector('.nav-toggle');
  const drawer = block.querySelector('.nav-drawer');

  toggle.addEventListener('click', () => {
    const isOpen = drawer.classList.toggle('is-open');
    document.body.classList.toggle('nav-open', isOpen);

    const main = document.querySelector('main');
    const footer = document.querySelector('footer');

    if (main) main.inert = isOpen;
    if (footer) footer.inert = isOpen;
  });
}

# CS / AMS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/clientlib-navigation/.content.xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          xmlns:sling="http://sling.apache.org/jcr/sling/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.navigation]"/>

# CS / AMS: page component HTL
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='example.navigation'}"/>

# CS / AMS: clientlib-navigation/js/navigation.js
function initNavigation() {
  const toggle = document.querySelector('.nav-toggle');
  const drawer = document.querySelector('.nav-drawer');

  if (!toggle || !drawer) return;

  toggle.addEventListener('click', () => {
    const isOpen = drawer.classList.toggle('is-open');
    document.body.classList.toggle('nav-open', isOpen);

    const main = document.querySelector('main');
    const footer = document.querySelector('footer');

    if (main) main.inert = isOpen;
    if (footer) footer.inert = isOpen;
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNavigation, { once: true });
} else {
  initNavigation();
}
```

**Why this is bad:** Setting the majority of the page as `inert` can have a significant performance cost when trying to animate a navigation drawer. Doing it in the input handler can block the interaction and incur an INP delay.

#### Approach: let the drawer paint before applying non-visual page state

```text
# EDS: blocks/navigation/navigation.js
export default function decorate(block) {
  const toggle = block.querySelector('.nav-toggle');
  const drawer = block.querySelector('.nav-drawer');

  toggle.addEventListener('click', () => {
    const isOpen = drawer.classList.toggle('is-open');
    document.body.classList.toggle('nav-open', isOpen);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const main = document.querySelector('main');
        const footer = document.querySelector('footer');
        const drawerIsOpen = drawer.classList.contains('is-open');

        if (main) main.inert = drawerIsOpen;
        if (footer) footer.inert = drawerIsOpen;
      });
    });
  });
}

# CS / AMS: ui.apps/src/main/content/jcr_root/apps/example/clientlibs/clientlib-navigation/.content.xml
<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
          xmlns:sling="http://sling.apache.org/jcr/sling/1.0"
          jcr:primaryType="cq:ClientLibraryFolder"
          categories="[example.navigation]"/>

# CS / AMS: page component HTL
<sly data-sly-use.clientlib="/libs/granite/sightly/templates/clientlib.html"
     data-sly-call="${clientlib.js @ categories='example.navigation'}"/>

# CS / AMS: clientlib-navigation/js/navigation.js
function initNavigation() {
  const toggle = document.querySelector('.nav-toggle');
  const drawer = document.querySelector('.nav-drawer');

  if (!toggle || !drawer) return;

  toggle.addEventListener('click', () => {
    const isOpen = drawer.classList.toggle('is-open');
    document.body.classList.toggle('nav-open', isOpen);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const main = document.querySelector('main');
        const footer = document.querySelector('footer');
        const drawerIsOpen = drawer.classList.contains('is-open');

        if (main) main.inert = drawerIsOpen;
        if (footer) footer.inert = drawerIsOpen;
      });
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNavigation, { once: true });
} else {
  initNavigation();
}
```

Use this when profiling shows that setting large page regions as `inert` contributes to a slow drawer interaction.

> **Source PRs** — **approach:** GoogleChrome/web.dev#9409, rancher/dashboard#5670