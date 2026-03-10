# SkellyCam Documentation

Documentation site for [SkellyCam](https://github.com/freemocap/skellycam), built with [Docusaurus](https://docusaurus.io/).

Live at: https://freemocap.github.io/skellycam/

## Development

```bash
cd skellycam-docs
npm install
npm start
```

Local dev server runs at `http://localhost:3000/skellycam/`.

## Build & Deploy

```bash
npm run build
```

Outputs static files to `build/`. Deployment to GitHub Pages happens via GitHub Actions.

---

## Connecting GitHub to the Docs

The docs site pulls live data from the GitHub repo. This section explains what
needs to happen on both sides when you want to surface something in the docs.

### The Roadmap page (`/roadmap`)

The roadmap page at `/roadmap` is a live dashboard that fetches GitHub Issues
and PRs from the repo. It requires **zero code changes** to add new items —
everything is driven by GitHub labels.

#### On GitHub: adding a roadmap item

1. Create (or find) the Issue or PR you want to show on the roadmap.
2. Add the **`roadmap`** label to it. That's it.

The roadmap page fetches all items with the `roadmap` label and displays them.
Any *other* labels on the item (e.g. `sync`, `streaming`, `timestamps`,
`infrastructure`) automatically become filter options on the page. Use labels
freely to organize — they all show up.

#### What the roadmap page shows

For each item, the page displays:

- **Type** — Issue or PR, auto-detected from the GitHub API response
- **Status** — Open or Closed
- **Title** — from the GitHub issue title
- **Excerpt** — first ~2 sentences of the issue body, stripped of markdown
- **Labels** — all labels except `roadmap` itself, shown as colored pills
- **Last updated date**
- **Link to GitHub** — clicking the card opens the issue/PR on GitHub

#### How caching works

The page uses a single GitHub API call with ETag-based conditional caching:

- **First visit** → 1 API request, response cached in localStorage with the ETag
- **Return within 5 minutes** → zero requests, served from cache
- **Return after 5 minutes** → conditional request with `If-None-Match` header.
  If nothing changed, GitHub returns 304 (does not count against rate limit).
  If something changed, fresh data is returned and cached.
- **API failure** → cached data is shown with a warning banner and retry button

The unauthenticated rate limit is 60 requests/hour per IP. With caching, a
single user generates at most 12 requests/hour even with aggressive page
reloading. Traffic spikes are handled by the 5-minute cache window.



### Core feature cards (index page + doc pages)

The index page shows feature cards that link to detailed doc pages under
`docs/core/`. These are driven by a shared data file, not by GitHub labels.

#### Adding a new core feature

1. **Add an entry to `src/data/core-features.tsx`:**

   Add a new object to the `CORE_FEATURES` array with `id`, `icon`, `title`,
   `description`, `summary` (JSX), `todos` (roadmap items), and `docPath`.

2. **Create a matching doc page at `docs/core/<id>.mdx`:**

   Use this template at the top:

   ```mdx
   ---
   sidebar_position: 5
   title: Your Feature Title
   description: One-line description for SEO.
   ---

   import CoreFeatureHeader from '@site/src/components/CoreFeatureHeader';
   import {getFeatureById} from '@site/src/data/core-features';

   <CoreFeatureHeader feature={getFeatureById('your-feature-id')} />

   ## Your content here...
   ```

   The `CoreFeatureHeader` renders the same summary + roadmap toggle that
   appears on the index card, creating visual consistency.

3. **That's it.** The index page card and sidebar entry both appear
   automatically.

#### Linking core feature roadmap items to GitHub

The `todos` array in each core feature entry has `issueNum` fields. These
should match real GitHub issue numbers. When you create the GitHub issue:

1. Create the issue on GitHub
2. Add the `roadmap` label (so it shows on the `/roadmap` page too)
3. Add any relevant topic labels (`sync`, `streaming`, etc.)
4. Put the issue number in the `todos` array in `core-features.tsx`

The TodoList component on the index cards links directly to
`github.com/freemocap/skellycam/issues/{issueNum}`.

---

## Project Structure

```
skellycam-docs/
├── docs/                          # Markdown/MDX documentation pages
│   ├── core/                      # Core concept pages (linked from index cards)
│   │   ├── _category_.json        # Sidebar group config ("Core Concepts")
│   │   ├── frame-perfect-sync.mdx
│   │   ├── generic-usb-cameras.mdx
│   │   ├── real-time-streaming.mdx
│   │   └── precise-timestamps.mdx
│   ├── intro.md
│   ├── architecture.md
│   └── ...
│
├── src/
│   ├── css/
│   │   ├── custom.css             # Docusaurus theme plumbing: --ifm-* and
│   │   │                          # --sk-* variable definitions, navbar/footer
│   │   │                          # overrides. No component styles.
│   │   └── theme.module.css       # ALL component and page styles. Imported as
│   │                              # `styles` everywhere. One file, dot-indexed.
│   ├── data/
│   │   ├── core-features.tsx      # Source of truth for index page feature cards
│   │   └── roadmap-types.ts       # Shared TypeScript types for roadmap data
│   │
│   ├── components/
│   │   ├── Tip.tsx                # Inline tooltip for progressive disclosure
│   │   ├── TodoList.tsx           # Collapsible roadmap toggle with GH issue links
│   │   ├── CoreFeatureHeader.tsx  # Summary block for top of core doc pages
│   │   ├── RoadmapEntry.tsx       # Single roadmap item card (reusable)
│   │   ├── RoadmapContent.tsx     # Roadmap dashboard: fetch, cache, filter, search
│   │   ├── AiGeneratedBanner.tsx  # "AI-generated" disclaimer for doc pages
│   │   └── DocFeedback.tsx        # Feedback widget for doc pages
│   │
│   ├── pages/
│   │   ├── index.tsx              # Landing page (hero + feature cards + guarantees)
│   │   ├── roadmap.tsx            # /roadmap route (Layout wrapper for RoadmapContent)
│   │   └── download.tsx           # /download route
│   │
│   └── theme/                     # Docusaurus theme overrides
│       └── DocItem/Layout/
│
├── static/                        # Static assets (images, download page)
├── docusaurus.config.ts           # Site config (navbar, footer, plugins)
├── sidebars.ts                    # Sidebar config (autogenerated from docs/)
└── package.json
```

## CSS Architecture

Two CSS files, clear separation:

- **`src/css/custom.css`** — Global, non-module. Required by Docusaurus for
  theme variable definitions (`--ifm-*`, `--sk-*`) and element overrides
  (navbar, footer, sidebar, code blocks). No component styles live here.

- **`src/css/theme.module.css`** — CSS Module imported by every component and
  page as `import styles from '@site/src/css/theme.module.css'`. All component
  and page styles live here. Class names are dot-indexed (`styles.heroTitle`,
  `styles.todoToggle`, `styles.roadmapCard`, etc.). Colors reference
  `var(--sk-*)` tokens from `custom.css`.

## GitHub Labels

The only label the docs care about is **`roadmap`**. Any issue or PR with
this label will appear on the `/roadmap` page.

All *other* labels on those items are auto-discovered and become filter
options on the roadmap page. Use whatever labels make sense for your
workflow — the docs will pick them up automatically.
