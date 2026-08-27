### Eager-load only the first visible images in a horizontal list

When a page has multiple above-the-fold images, mark only the images that are visible without scrolling as eager-loaded. This keeps the browser from treating every card image as high priority and preserves lazy-loading for the rest.

```html
<!-- Good -->
<ul class="horizontal-list">
  <li>
    <img src="city-1.jpg"
         alt="Travel"
         fetchpriority="high"
         loading="eager"
         width="120"
         height="120">
  </li>
  <li>
    <img src="city-2.jpg"
         alt="Travel"
         loading="lazy"
         width="120"
         height="120">
  </li>
</ul>
```

Use this for carousels, horizontal feeds, and mobile home sections where only the first few items are initially visible.

**Why this is good:** It gives the browser a clear signal for the images that are actually visible on initial load, while keeping the rest of the list lazy-loaded to avoid unnecessary network contention.