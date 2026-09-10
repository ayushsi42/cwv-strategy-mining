applicable_flavors for the playbook this content is being added to: ['eds', 'cs', 'ams']

## Prefer system fonts outside narrowly scoped custom-font use

### Anti-pattern: making a custom font a site-wide dependency

```css
/* Bad: every page depends on the web font, including pages that do not need it. */
html {
  font-family: "Site Sans", Arial, sans-serif;
}

@font-face {
  font-family: "Site Sans";
  src: url("resources/site-sans.woff2") format("woff2");
  font-display: swap;
}
```

**Why this is bad:** This makes the custom font the default font for the site, including components that could use a platform font stack instead.

### Approach: use a platform stack by default and scope web fonts to the component that needs them

```text
# EDS: /styles/styles.css
@import url("./base.css");
@import url("./fonts.css");

# CS/AMS: /apps/my-site/clientlibs/site-base/css.txt
base.css
fonts.css
```

```css
/* base.css */
html {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, "Noto Sans", "Liberation Sans", sans-serif;
}

/* fonts.css */
@font-face {
  font-family: "Site Code";
  src: url("resources/site-code.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

.cmp-code-output code {
  font-family: "Site Code", SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;
}
```

Preload a scoped font when it is needed for page rendering. Use a font preload with `as="font"`, an appropriate font `type`, and `crossorigin="anonymous"` where applicable.

> **Source PRs** — **approach:** htmlacademy-adaptive/2280491-cat-energy-28#9, jakearchibald/svgomg#339, voorhoede/head-start#209, mongodb/snooty#1050