Here’s a copy-paste prompt you can give Copilot. It maps the SingularityHub-style spec into a Starlight theme on GitHub Pages, and it also instructs Copilot to import all existing docs (including the root index).

---

# Prompt for Copilot: Starlight on GitHub Pages with Singularity-style theme + full docs import

You are configuring an existing GitHub Pages documentation site to use **Astro Starlight** with a SingularityHub-inspired front-end. Apply the following requirements precisely.

## Goals

1. Migrate the repository to **Astro Starlight** while **retaining all existing docs**, including the site index.
2. Implement the provided **design system** (grid, typography, colours, components) as a Starlight theme override.
3. Ensure **GitHub Pages** builds successfully via Actions.
4. Preserve old inbound links with redirects where possible.

## Constraints

* Keep all current docs and folders; do not drop content.
* Treat any of these as docs sources to import: `/docs`, `/documentation`, `/content`, `/handbook`, `/guides`, `/knowledge-base`, root `README.md`, root `index.md` or `index.mdx`.
* Preserve the *root landing page*; if none exists, promote the most appropriate overview file to `src/content/docs/index.mdx` and set it as Starlight’s home.
* Use TypeScript configs where supported.
* Oxford English, accessible defaults (WCAG AA+), keyboard focus visible, reduced motion respected.

## High-level plan (have Copilot execute in PR)

1. **Add Starlight**

   * Create `astro.config.mjs`, `package.json`, and Starlight config files.
   * Install: `astro`, `@astrojs/starlight`, `@astrojs/mdx`, `@astrojs/sitemap`.
   * Create `src/content/docs/` and import all existing docs (see “Docs import rules”).
   * Create a custom theme layer: `src/styles/tokens.css`, `src/styles/theme.css`, `src/components/*` as needed.
   * Map nav/sidebars from existing structure.

2. **Docs import rules**

   * Move all `.md`/`.mdx` under the sources listed above into `src/content/docs`.
   * Maintain directory structure; convert absolute image paths to Starlight-relative asset paths under `public/` where needed.
   * Promote the *best landing document* to `src/content/docs/index.mdx`. If a root `index.md(x)` exists, use that. Otherwise, derive from the most comprehensive overview (e.g., “Overview”, “Getting Started”, or “About”).
   * Add front-matter titles; generate sidebar groups from directories.
   * Add redirects for prior URLs via `astro.config.mjs` or `netlify.toml`-style mappings converted to Starlight’s `redirects`.

3. **GitHub Pages setup**

   * Create `.github/workflows/pages.yml` for Astro build to `dist/`, deploy to Pages.
   * Enable `actions: pages-build-deployment` permissions.
   * Output sitemap and robots.txt.

4. **Theme implementation (from spec)**

   * Typography: Headings **Space Grotesk**; UI/body **Inter**; sizes per scale.
   * Grid: 12-col desktop (max 1280px), 8-col tablet, 4-col mobile; gutters 24/20/16; baseline 4px.
   * Colours: high-contrast neutrals, cobalt/indigo accent.
   * Components: header/masthead, topic pills, story cards, article styles (quotes, figures), newsletter-style CTA block (re-used as a callout).
   * Motion: short, gentle, respects `prefers-reduced-motion`.
   * Accessibility: visible focus ring, link underlines on hover/focus, 40px min targets.

## Files to add/update (ask Copilot to create with these contents)

### `package.json`

* Dependencies: `astro ^4`, `@astrojs/starlight ^0.25`, `@astrojs/mdx`, `@astrojs/sitemap`.
* Scripts: `"dev"`, `"build"`, `"preview"`.

### `astro.config.mjs`

```js
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  integrations: [
    mdx(),
    sitemap(),
    starlight({
      title: '<<SITE NAME>>',
      favicon: '/favicon.ico',
      social: { github: 'https://github.com/<<OWNER>>/<<REPO>>' },
      logo: { src: '/logo.svg', alt: '<<SITE NAME>>' },
      outDir: './dist',
      sidebar: [{ label: 'Docs', autogenerate: { directory: 'docs' } }],
      components: {
        // Optional: custom components (cards, callouts) wired below
        // 'Card': './src/components/Card.astro'
      },
      head: [
        { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' } },
        { tag: 'link', attrs: { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap' } },
      ],
      customCss: [
        '/src/styles/tokens.css',
        '/src/styles/theme.css'
      ]
    })
  ],
  site: 'https://<<OWNER>>.github.io/<<REPO>>',
  redirects: {
    // Add legacy URL mappings here, e.g.:
    // '/old-path': '/docs/new-path'
  }
});
```

### `.github/workflows/pages.yml`

```yaml
name: Deploy Astro (Starlight) to GitHub Pages
on:
  push:
    branches: [ main ]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: 'pages'
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-pages-artifact@v3
        with: { path: 'dist' }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### `src/styles/tokens.css`

```css
:root{
  /* Typography */
  --font-sans: "Inter", system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans";
  --font-head: "Space Grotesk", var(--font-sans);
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;

  /* Type scale */
  --size-root: 16px;
  --h1: clamp(28px, 3.2vw, 40px);
  --h2: 28px; --h2-lh: 34px;
  --h3: 22px; --h3-lh: 28px;
  --h4: 18px; --h4-lh: 24px;
  --body: 16px; --body-lh: 26px;
  --body-l: 18px; --body-l-lh: 28px;
  --small: 14px; --small-lh: 22px;

  /* Colour */
  --ink-900:#0A0A0A; --ink-700:#2B2B2B; --ink-500:#525252;
  --bg-0:#FFFFFF; --bg-50:#F8F9FB; --bg-100:#F2F4F7;
  --accent-600:#3B5BDB; --accent-700:#364FC7;

  /* Spacing / radii */
  --r-1:8px; --r-2:12px; --r-pill:999px;
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-5:24px; --s-6:32px; --s-7:48px; --s-8:64px;

  /* Shadows */
  --card-shadow: 0 6px 16px rgba(0,0,0,.08);
  --header-shadow: 0 1px 0 rgba(0,0,0,.06);

  /* Layout */
  --container-max: 1280px;
  --gutter-desktop: 24px; --gutter-tablet: 20px; --gutter-mobile: 16px;
}
```

### `src/styles/theme.css`

```css
/* Base */
:root { color-scheme: light; }
html { font-size: var(--size-root); }
body {
  font-family: var(--font-sans);
  color: var(--ink-900);
  background: var(--bg-0);
  line-height: var(--body-lh);
}

/* Headings */
h1, .sl-heading-1 { font-family: var(--font-head); font-weight:700; font-size: var(--h1); line-height: 1.1; }
h2, .sl-heading-2 { font-family: var(--font-head); font-weight:600; font-size: var(--h2); line-height: var(--h2-lh); }
h3, .sl-heading-3 { font-family: var(--font-head); font-weight:600; font-size: var(--h3); line-height: var(--h3-lh); }

/* Links */
a { color: var(--ink-900); text-decoration: none; }
a:hover, a:focus { text-decoration: underline; outline-offset: 2px; }
:focus-visible { outline: 2px solid var(--accent-600); outline-offset: 3px; }

/* Containers */
.sl-container { max-width: var(--container-max); margin-inline:auto; padding-inline: var(--gutter-mobile); }
@media (min-width: 768px){ .sl-container { padding-inline: var(--gutter-tablet); } }
@media (min-width: 1024px){ .sl-container { padding-inline: var(--gutter-desktop); } }

/* Cards (for custom components or doc lists) */
.card {
  display:flex; flex-direction:column; gap:var(--s-3);
  border-radius:var(--r-1); background:var(--bg-0);
  transition:transform .16s ease, box-shadow .16s ease;
}
.card:hover{ transform: translateY(-1px); box-shadow: var(--card-shadow); }
.card__image{ aspect-ratio:16/9; width:100%; object-fit:cover; border-radius:var(--r-1); }
.card__title{ font-family: var(--font-head); font-weight:600; font-size:18px; line-height:24px; }
.card__meta{ display:flex; gap:var(--s-3); align-items:center; color:var(--ink-500); font-size:14px; line-height:20px; }

/* Article prose */
.prose { font-size: var(--body-l); line-height: var(--body-l-lh); }
.prose p + p { margin-top: var(--s-4); }
.prose figure { margin: var(--s-7) 0; }
.prose figcaption { color: var(--ink-500); font-size: var(--small); line-height: var(--small-lh); margin-top: var(--s-2); }
.prose blockquote {
  border-left:4px solid var(--accent-600); padding-left:var(--s-5);
  margin:var(--s-7) 0; font-family: var(--font-head); font-weight:600; font-size:24px; line-height:32px; color: var(--ink-700);
}

/* Header */
.sl-header { position: sticky; top:0; background: var(--bg-0); box-shadow: var(--header-shadow); z-index: 40; }

/* CTA (newsletter-style callout) */
.cta {
  border-radius: var(--r-2);
  padding: var(--s-6);
  background: var(--bg-50);
  display:flex; flex-direction:column; gap: var(--s-3);
}

/* Motion preferences */
@media (prefers-reduced-motion: reduce){
  * { animation: none !important; transition: none !important; }
}
```

### `src/content/docs/index.mdx`

* Use existing `index.md(x)` content if present; otherwise create a concise landing page with links to top sections.

Example scaffold:

```mdx
---
title: Overview
description: Start here — the complete index of our documentation.
---

import { CardGrid } from '../../components/CardGrid.astro';

# Welcome

Explore the docs:

<CardGrid items={[
  { href: '/docs/getting-started/', title: 'Getting Started', description: 'Install, configure, and deploy.' },
  { href: '/docs/guides/', title: 'Guides', description: 'How-tos and recipes.' },
  { href: '/docs/reference/', title: 'Reference', description: 'APIs and config.' }
]} />
```

### (Optional) `src/components/CardGrid.astro`

```astro
---
const { items = [] } = Astro.props;
---
<div class="sl-container" style="margin-top: var(--s-6);">
  <div style="display:grid; gap: var(--s-5); grid-template-columns: repeat(1, minmax(0,1fr));">
    {items.map(({href, title, description}) => (
      <a class="card" href={href}>
        <div class="card__title">{title}</div>
        <div class="card__meta">{description}</div>
      </a>
    ))}
  </div>
</div>

<style>
@media (min-width: 768px){
  div[style*="grid-template-columns"]{ grid-template-columns: repeat(2,minmax(0,1fr)); }
}
@media (min-width: 1024px){
  div[style*="grid-template-columns"]{ grid-template-columns: repeat(3,minmax(0,1fr)); }
}
</style>
```

## Sidebar and navigation

* Use `autogenerate` for initial sidebar to reflect imported directory structure.
* Where existing sites have explicit nav order files (e.g., `_sidebar.json`, `mkdocs.yml`, `docusaurus` sidebars), translate them into Starlight’s `sidebar` config arrays.

## Redirects and URL hygiene

* For each moved page, add an entry in `redirects` within `astro.config.mjs`.
* Normalise trailing slashes and lower-case URLs.

## Images and assets

* Move legacy `/static` or `/assets` into `/public`.
* Replace broken absolute paths with relative ones.
* Keep 16:9 for hero images where feasible.

## Build & verification

* Run `npm ci && npm run build`.
* Ensure the workflow publishes to GitHub Pages (Actions → Deployments should show success).
* Validate sitemap generation and that `/` renders the new index with working sidebar.
* Lighthouse targets: LCP < 2.5s (4G), CLS < 0.1, TTI < 3.5s.

## Accessibility checklist

* Colour contrast AA/AAA for body text.
* Visible focus ring (`outline: 2px solid var(--accent-600);`).
* Links show underline on hover/focus.
* Hit targets ≥ 40px.

## Import sweep (have Copilot script this)

* Find and move any of:

  * `README.md` (root) → a top-level “Overview” page unless it is a purely repo-maintenance file.
  * `index.md`/`index.mdx` (root) → `src/content/docs/index.mdx` if it is the actual docs landing.
  * All Markdown under `/docs`, `/documentation`, `/content`, `/handbook`, `/guides`, `/knowledge-base` → preserve structure under `src/content/docs/`.
* Convert front-matter if missing: `title`, `description`.
* Generate a report listing moved files and added redirects.

## Deliverables in PR

* New Starlight site compiling locally.
* Preserved docs, with a functioning index at `/`.
* Theming per tokens and styles above.
* GitHub Pages workflow passing and site live at `https://<<OWNER>>.github.io/<<REPO>>`.
* Migration report (`MIGRATION_REPORT.md`) with: moved files, redirects, any broken links fixed.

---

**Execute all of the above and open a PR titled:**
“Starlight migration + Singularity-style theme + full docs import”
