---
issue_type: javascript-delivery--lazy-load-noncritical-client-modules
parent_strategy: javascript-delivery
risk_tier: low
cwv_metrics: [bundle_size_delta_pct]
source_prs:
  - ColeMurray/background-agents#373
  - ant-design/x#1233
  - module-federation/core#4449
required_validation:
  - markdown_code_blocks_present
  - syntax_highlight_theme_loaded_client_side
  - rehype_highlight_added_before_sanitize
forbidden_techniques: []
---
# Lazy-load noncritical client modules

> **Risk tier:** low · **Parent strategy:** javascript-delivery · **CWV metric:** `bundle_size_delta_pct`

## Strategy summary

This strategy reduces initial client delivery cost by deferring noncritical client modules until the page actually needs them.

The supplied evidence supports two concrete instances of this mechanism:

1. **Markdown code highlighting**
   - `rehype-highlight` is added to the markdown rendering pipeline.
   - Highlight.js theme CSS is loaded on the client based on the resolved color scheme.
   - Inline code is rendered separately from highlighted code blocks.

2. **Noncritical animation components**
   - A banner animation component is imported with `React.lazy`.
   - The component is mounted only when the UI reaches the relevant state or viewport condition.

This playbook focuses on the shared delivery mechanism: move optional client work out of the initial bundle path and load it only when needed.

## Evidence

### Improvement evidence

#### `ColeMurray/background-agents#373`
Changed files show a markdown rendering path that adds syntax highlighting and client-side theme loading:

- `packages/web/src/components/safe-markdown.tsx`
  - imports `rehype-highlight`
  - keeps `rehype-sanitize` in the pipeline
  - distinguishes highlighted code blocks from inline code
- `packages/web/src/components/syntax-highlight-theme.tsx`
  - loads `/hljs-themes/atom-one-light.css` or `/hljs-themes/atom-one-dark.css` in a client effect
  - swaps theme stylesheets by manipulating `<link>` elements in `document.head`
- `packages/web/public/hljs-themes/*.css`
  - theme CSS is served as static assets rather than bundled into the markdown component

This source does not include a measured bundle delta in the packet, but it provides direct implementation evidence for lazy-loading a noncritical client module.

#### `ant-design/x#1233`
Changed files show a broader lazy-load pattern for optional client modules:

- `packages/x/.dumi/pages/index/components/DesignBanner.tsx`
  - replaces eager animation usage with `React.lazy`
  - mounts the animation component inside `Suspense`
- `packages/x/.dumi/pages/index/components/MainBanner.tsx`
  - lazy-loads animation components
  - defers animation behavior until load-time callbacks run
- `packages/x/.dumi/hooks/useLottie.ts`
  - adjusts animation instance handling to support the new loading model

Measured evidence in the packet:
- `bundle_size_delta_pct`: delta `-85.48`
- directional consistency: `100.0%` improvements across 3 observations
- statistical support: 3 observations across 3 repositories
- confidence: medium

### Inference from evidence

- Deferring syntax highlighting and animation components is a valid instance of lazy-loading noncritical client modules.
- Client-side theme stylesheet loading is part of the same delivery mechanism because it keeps theme CSS out of the initial component path.
- The strategy is low risk because it changes when optional client work loads, not the content model or rendering semantics.

## When to apply

Apply this strategy when all of the following are true:

- the page renders optional client functionality that is not required for first paint
- the module can be loaded only when a feature, viewport condition, or content type requires it
- the initial bundle contains code that can be deferred without changing correctness
- the deferred module can be mounted or invoked after the page has already become usable

## When to skip

Skip this strategy when any of the following are true:

- the module is required for initial correctness or first meaningful render
- the code path is already server-only and there is no client bundle to reduce
- deferring the module would break sanitization, security, or content integrity
- the feature is always visible and always needed immediately
- the implementation would require unsupported assumptions about framework internals

## Required validation

### `markdown_code_blocks_present`

**What this validates:** the markdown path still contains code blocks that should receive syntax highlighting.

**How to verify:**
- Render markdown that includes fenced code blocks.
- Confirm fenced blocks are still passed through the markdown renderer.
- Confirm inline code is still rendered separately from fenced blocks.

**Why it matters:** lazy-loading the highlighter only makes sense if there is a real code-sample rendering path to defer.

---

### `syntax_highlight_theme_loaded_client_side`

**What this validates:** the highlight theme stylesheet is loaded on the client after theme resolution.

**How to verify:**
- Confirm a client component reads the resolved theme.
- Confirm it creates a `<link rel="stylesheet">` element in `document.head`.
- Confirm the stylesheet `href` is selected from a theme map.
- Confirm the old stylesheet is removed after the new one loads, with a fallback cleanup path.

**Why it matters:** the evidence shows theme CSS is not statically imported into the markdown component; it is loaded only when the client resolves the active theme.

---

### `rehype_highlight_added_before_sanitize`

**What this validates:** syntax highlighting is inserted into the markdown pipeline before sanitization.

**How to verify:**
- Confirm `rehype-highlight` appears in the `rehypePlugins` list.
- Confirm sanitization still runs after highlighting.
- Confirm the sanitization schema remains in place.

**Why it matters:** the evidence preserves the security boundary by keeping sanitization in the pipeline after highlighting.

## Evidence-derived implementation pattern

### Good: add highlighting before sanitization

```tsx
"use client";

import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";

const sanitizeSchema = defaultSchema;

export function SafeMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight, [rehypeSanitize, sanitizeSchema]]}
    >
      {content}
    </ReactMarkdown>
  );
}
```

### Good: load highlight theme CSS on the client

```tsx
"use client";

import { useTheme } from "next-themes";
import { useEffect } from "react";

const HLJS_THEMES: Record<string, string> = {
  light: "/hljs-themes/atom-one-light.css",
  dark: "/hljs-themes/atom-one-dark.css",
};

export function SyntaxHighlightTheme() {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const href = HLJS_THEMES[resolvedTheme ?? "light"] ?? HLJS_THEMES.light;
    const existing = document.querySelector("link[data-hljs-theme]") as HTMLLinkElement | null;
    if (existing?.getAttribute("href") === href) return;

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.setAttribute("data-hljs-theme", "true");

    link.onload = () => existing?.remove();
    document.head.appendChild(link);

    const timer = existing ? setTimeout(() => existing.remove(), 100) : undefined;

    return () => {
      clearTimeout(timer);
      link.remove();
    };
  }, [resolvedTheme]);

  return null;
}
```

### Good: keep inline code separate from highlighted blocks

```tsx
code: ({ className, children, ...props }) => {
  if (className) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  return (
    <code
      className="font-mono bg-muted border border-border rounded px-1.5 py-0.5 text-[0.85em]"
      {...props}
    >
      {children}
    </code>
  );
}
```

### Good: lazy-load optional animation components

```tsx
import React, { lazy, Suspense } from "react";

const LottieComponent = lazy(() => import("./Lottie"));

export function Banner() {
  return (
    <Suspense>
      <LottieComponent path="https://example.invalid/animation.json" />
    </Suspense>
  );
}
```

## Verification

Use the supplied metric: `bundle_size_delta_pct`.

### Measurable checks
- Compare bundle size before and after the lazy-load change.
- Confirm the client bundle no longer includes the deferred module in the initial path.
- Confirm the deferred module is loaded only when the relevant content or UI state is present.

### Behavioral checks
- Markdown code blocks still render correctly.
- Inline code still renders with separate inline styling.
- Highlight theme CSS changes with the resolved theme.
- Sanitization still runs after highlighting.
- Optional animation or media modules still appear when their trigger condition is met.

## Anti-patterns

No concrete forbidden regex is justified by the supplied evidence. The evidence supports the mechanism, not a universal textual pattern. Use code review and bundle inspection instead of regex-based enforcement.

## Risks and limitations

- This strategy only helps when the deferred module is truly noncritical.
- Client-side stylesheet swapping must avoid leaving stale theme links behind.
- Plugin order matters: highlighting must not bypass sanitization.
- The measured bundle improvement in the packet is directional evidence, not a fixed target for every repository.
- The exact `bundle_size_delta_pct` depends on the surrounding bundle graph and how much code was previously eager.

## Evidence and confidence

### Observed facts
- `ColeMurray/background-agents#373` adds `rehype-highlight` to the markdown rendering path.
- The same source loads highlight.js theme CSS on the client from `/hljs-themes/`.
- The same source keeps sanitization in the markdown pipeline after highlighting.
- `ant-design/x#1233` uses `React.lazy` and `Suspense` to defer optional animation components.
- `ant-design/x#1233` is associated with a measured `bundle_size_delta_pct` improvement and consistent directional improvement across observations.

### Inference
- Loading syntax highlighting only when markdown is rendered is a valid instance of lazy-loading a noncritical client module.
- Client-side theme stylesheet swapping is part of the same mechanism because it avoids static inclusion of theme CSS in the initial path.
- The strategy is low risk because it preserves rendering semantics and only changes when optional client work is loaded.

### Confidence
Medium. The evidence is consistent across the supplied sources, but the measured data is limited and the exact bundle impact depends on the surrounding client bundle composition.

## Evidence sample note

This document's `source_prs` list above reflects every PR actually supplied as generation evidence for this strategy (3 PRs). It is a bounded representative sample, not the full evidence base: the mining pipeline recorded **3 observations across 3 repositories** for this technique in total (see `data/processed/technique_aggregates.jsonl`, `canonical_id: javascript-delivery--lazy-load-noncritical-client-modules`). Only a capped sample of representative PRs is retained and linked per technique; the statistics elsewhere in this document (Confidence / Evidence sections) describe that full observation set, not just the PRs cited by id.
