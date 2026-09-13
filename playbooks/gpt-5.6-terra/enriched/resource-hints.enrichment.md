### Consider where a preconnect is added

A preconnect tells the browser to start resolving DNS and establishing an SSL connection before a later request. The evidence shows this being added for origins that are expected to receive token or font requests.

**Example placement to review:**

```js
// blocks/hero/hero.js
export default async function decorate(block) {
  const origin = block.dataset.criticalOrigin;

  const preconnect = document.createElement('link');
  preconnect.rel = 'preconnect';
  preconnect.href = origin;
  document.head.append(preconnect);

  const response = await fetch(`${origin}/hero-content.json`);
  const content = await response.json();

  block.innerHTML = `<h1>${content.title}</h1>`;
}
```

**Why this placement may not provide the intended benefit:** The evidence describes preconnect as starting DNS resolution and SSL connection establishment before a later request. When the hint and request are added together, the request may not wait for those steps to complete.

**Example of a document-head placement:**

```html
<!-- Initial document head -->
<link rel="preconnect" href="https://images.example.com">
```

```js
// blocks/hero/hero.js
export default function decorate(block) {
  const image = document.createElement('img');
  image.src = 'https://images.example.com/hero/banner.webp';
  image.alt = block.dataset.alt || '';

  block.replaceChildren(image);
}
```

The evidence includes `crossorigin` on preconnect links for Google Fonts origins.

> **Source PRs** — **approach:** Amen-Musingarimi/Microverse-Portfolio-Mobile#1, AzureAD/microsoft-authentication-library-for-js#6550 · **anti-pattern:** lifeisbeautifu1/modern-react-app#47, lifeisbeautifu1/modern-react-app#66