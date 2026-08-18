---
issue_type: network-payload
risk_tier: low
source_prs: [ant-design/ant-design#54746, ant-design/x#1115, Jujulego/jill#1258, ant-design/x#1121, ant-design/x#1198]
---
# Reduce shipped payload by removing unused runtime dependencies and non-runtime files

## What this addresses
This technique reduces what users download, parse, and execute by trimming shipped package contents and runtime dependencies. The evidence shows several forms of payload reduction:

- removing a runtime styling dependency and related code
- excluding non-runtime files from distributed package output
- removing an extra chunk and unused runtime imports
- removing unused runtime packages from the shipped dependency surface

## Evidence
- **ant-design/ant-design#54746**: the patch removes a runtime styling dependency and related code paths. In the diff, `antd-style` usage is removed from `components/actions/ActionsFeedback.tsx`, including the `createStyles` block, and the component is rewritten to use existing class names instead of generated styles.
  - Example patch evidence:
    - `- import { Space, Tooltip } from 'antd';`
    - `- import { createStyles } from 'antd-style';`
    - `- const useStyles = createStyles(...)`
    - `- <Space ...>`
    - `+ <div ...>`

- **ant-design/x#1115**: the patch excludes non-runtime files from package distribution and adjusts build inputs.
  - Example patch evidence:
    - `.gitignore` adds package/version and docs-template paths such as:
      - `packages/x/components/version/version.ts`
      - `packages/x-markdown/src/version.ts`
      - `packages/x-sdk/src/version/version.ts`
    - `packages/x-markdown/.fatherrc.ts` adds:
      - `ignores: ['**/__tests__/**']`
      - `cjs: { ignores: ['**/__tests__/**'] }`
    - `packages/x-markdown/package.json` changes `predist`/`pretest` to run `prestart`, which generates version/plugin metadata before packaging.

- **Jujulego/jill#1258**: the patch removes an extra chunk and an unused runtime import.
  - Example patch evidence:
    - `rollup.config.js` removes `manualChunks` for `parser`
    - `src/main.ts` changes:
      - `import { captureException, captureMessage, startSpan } from '@sentry/node';`
      - to `import { captureException, startSpan } from '@sentry/node';`
    - `captureMessage(msg, { level: 'error' });` is removed from the error path

- **ant-design/x#1121**: the patch continues the package-output cleanup by moving version files and adjusting ignore rules so only runtime-relevant files are shipped.
  - Example patch evidence:
    - `.gitignore` changes `packages/x-markdown/src/version.ts` to `packages/x-markdown/src/version/version.ts`
    - `biome.json` narrows rule scopes for source trees
    - `packages/x-markdown/src/version/version.ts` is present as a generated version file path

- **ant-design/x#1198**: the patch removes unused runtime packages from `packages/x-markdown/package.json`.
  - Example patch evidence:
    - `- "@react-spring/web": "^10.0.1",`
    - `- "html-tags": "^3.3.1",`
    - `AnimationNode.tsx` removes `@react-spring/web` imports and replaces spring-based animation with local fade logic
    - `src/index.ts` and `src/XMarkdown/interface.ts` are updated to export the new local types and animation config

## Recommended approach
- Remove runtime dependencies that are no longer needed by shipped code.
- Exclude tests, templates, generated metadata, and other non-runtime files from package output.
- Remove unused imports, helper code, and extra chunks when they no longer contribute to runtime behavior.
- Keep the shipped entry surface focused on the code consumers actually import and execute.

## Risks and limitations
- Payload reduction can change runtime behavior if a removed dependency or file was still indirectly relied on.
- Excluding files from distribution requires care to avoid omitting generated assets that are still needed at runtime.
- Replacing a dependency with local logic may reduce payload but can also shift maintenance burden into the package itself.

## Anti-pattern evidence
Regression evidence is absent in the supplied PRs. The provided patches are all improvement-side examples of payload reduction, and no source excerpt shows a regression caused by this technique.