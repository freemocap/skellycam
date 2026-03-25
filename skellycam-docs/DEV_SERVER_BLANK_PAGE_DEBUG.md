# Blank Page on Dev Server Startup — Debug Guide

## The Problem

When running `npm start` (i.e. `docusaurus start`) in the `skellycam-docs/` directory, the dev server starts and compiles successfully, but the browser shows a **blank dark page**. An error may flash briefly on screen before being replaced by the dark background.

The production build (`npm run build && npm run serve`) works fine.

## Observed Behavior

- Server starts, webpack compiles successfully, no server-side errors
- Browser navigates to `http://localhost:3000/skellycam/` (note the baseUrl)
- Page title is "SkellyCam" (so the HTML shell loads)
- The `<body>` contains HTML (~1367 bytes) but `innerText` is empty — React mounts but renders nothing visible
- No persistent console errors (the error that flashes may be caught/swallowed by an error boundary)
- The dark background comes from the Docusaurus dark theme (`colorMode.defaultMode: 'dark'`)

## Likely Cause: HMR / Client-Side Hydration Failure

The flash-of-error-then-blank pattern is classic for a **React hydration or initialization crash** caught by Docusaurus's error boundary, which renders nothing (dark background). Possible triggers:

### 1. React 19 + Docusaurus 3.9.2 Compatibility

`package.json` specifies `react: ^19.0.0`. Docusaurus 3.9.2 was built for React 18. React 19 changed hydration behavior and error handling. This is the most likely culprit.

**Quick test:** Downgrade React to 18:
```bash
npm install react@18 react-dom@18
npm start
```

### 2. `@freemocap/skellydocs` (v0.3.8) SSR Issue

The home page (`src/pages/index.tsx`) renders:
```tsx
import { IndexPage } from '@freemocap/skellydocs';
import config from '../../content.config';

export default function Home() {
  return <IndexPage config={config} />;
}
```

`content.config.tsx` contains JSX in its `summary` fields (using `<Tip>`, `<strong>`, `<em>`). If the `@freemocap/skellydocs` package has an SSR issue — e.g., accessing `window` or `document` during server rendering — it would crash during Docusaurus's dev-mode SSR/hydration step.

**Quick test:** Replace index.tsx temporarily with a plain component:
```tsx
import Layout from '@theme/Layout';

export default function Home() {
  return (
    <Layout title="SkellyCam">
      <div style={{ padding: 40 }}>
        <h1>Test Page</h1>
        <p>If you can see this, the issue is in IndexPage or content.config.</p>
      </div>
    </Layout>
  );
}
```

### 3. Webpack `disableFullySpecified` Plugin + HMR Interaction

`docusaurus.config.ts` has a custom webpack plugin:
```ts
function disableFullySpecified() {
  return {
    name: 'disable-fully-specified',
    configureWebpack() {
      return {
        module: {
          rules: [{ test: /\.m?js$/, resolve: { fullySpecified: false } }],
        },
      };
    },
  };
}
```

This relaxes ESM resolution for the `@freemocap/skellydocs` tsup output. It's needed for the build, but could theoretically interact badly with webpack-dev-server's HMR module resolution.

**Quick test:** Temporarily remove the plugin from `docusaurus.config.ts` plugins array and see if the page loads (it may break imports from skellydocs, but will tell you if this plugin causes the blank page).

### 4. CSS Loading Race / Flash of Error

The site loads two external CSS sources:
- `@freemocap/skellydocs/css/custom.css` (from node_modules)
- Google Fonts stylesheet (external URL)

If the custom CSS fails to load or has a parse error in dev mode, the page might render with broken styles. The download page specifically had a `z-index: 999` on a fixed pseudo-element covering everything (now fixed to `z-index: 0`), but the home page relies on styles from the npm package.

### 5. Stale `.docusaurus` Cache

Docusaurus caches generated routes and webpack state in `.docusaurus/`. A stale cache after dependency updates can cause hydration mismatches.

**Quick test:**
```bash
npm run clear
npm start
```

## Debugging Steps (Recommended Order)

1. **Clear cache first** — eliminates the easy cause:
   ```bash
   cd skellycam-docs
   npm run clear
   npm start
   ```

2. **Check the browser console immediately on load** — the error flashes briefly, so open DevTools *before* navigating to the page. Look for:
   - React hydration mismatch errors
   - Module import failures
   - `ReferenceError: window is not defined` (SSR issue)
   - `TypeError` from skellydocs components

3. **Test with plain index page** — isolate whether the crash is in `IndexPage`/`content.config` or in Docusaurus itself (see code above in section 2)

4. **Check React version compatibility** — if plain page works, try downgrading React (see section 1)

5. **Check if MDX docs pages load** — navigate directly to `http://localhost:3000/skellycam/docs/intro` instead of the home page. If docs pages render but the home page doesn't, the issue is specifically in the custom pages/components.

## Key Files

| File | Role |
|------|------|
| `docusaurus.config.ts` | Site config — baseUrl `/skellycam/`, dark mode default, custom webpack plugin, i18n |
| `package.json` | Dependencies — React 19, Docusaurus 3.9.2, @freemocap/skellydocs ^0.3.8 |
| `content.config.tsx` | Home page content config — contains JSX with `<Tip>` components in summary fields |
| `src/pages/index.tsx` | Home page — renders `<IndexPage config={config} />` from skellydocs |
| `src/pages/download.tsx` | Download page — wraps `<DownloadPage />` in Layout |
| `src/pages/roadmap.tsx` | Roadmap page — renders `<RoadmapPage>` from skellydocs |
| `src/css/sidebar.css` | Local sidebar style overrides |
| `src/components/download/DownloadPage.tsx` | Download page component (fetches GitHub releases, detects OS) |
| `src/components/download/DownloadPage.module.css` | Download page styles (z-index on `::before` was recently fixed from 999 to 0) |

## Environment

- Node.js v22.22.0
- Windows 11
- Docusaurus 3.9.2 (classic preset + mermaid theme)
- React 19.0.0
- @freemocap/skellydocs ^0.3.8
- TypeScript ~5.6.2

## What Works

- `npm run build` completes successfully for all 4 locales (en, es, ar, zh-CN)
- `npm run serve` (serving the production build) — should work (untested this session)
- No broken links in the English build
