# Executive Take

You can closely match AQRisk’s dark, high-contrast, minimalist fintech aesthetic—confident typography, navy/mint palette—using Astro Starlight. Achieve this by:

1. Setting a navy/mint palette via Starlight’s CSS variables.
2. Crafting a custom `index.astro` hero and “solutions” card grid.
3. Adding a reusable Testimonials content collection.
4. Overriding select Starlight components for a cleaner header/CTA.

AQRisk’s site uses a split hero, value-driver sections, client quotes, and long “solution” pages—patterns you can mirror in Starlight.

---

## Distilling the AQRisk Aesthetic

- **Palette:** Very dark blue canvas, bright teal/mint accent, generous white/near-white text, subtle image tiles.
- **Hero:** Oversized multi-line headline, single primary CTA, understated supporting line, light imagery.
- **Sections:** “Top value-drivers” and “Solution features” as cards/accordions with numbered anchors; long, scannable solution pages.
- **Social Proof:** Rotating client quotes with roles, sprinkled across pages.

---

## Translating to Starlight: Step-by-Step

### 1. Set the Colour System (Dark-first, Mint Accent)

Create `src/styles/theme.css` and override Starlight’s CSS variables:

```css
:root[data-theme="dark"] {
  /* Canvas & text */
  --sl-color-bg: oklch(14% 0.02 240); /* deep navy */
  --sl-color-text: oklch(92% 0.02 240); /* near-white */
  --sl-color-gray-6: oklch(55% 0.02 240); /* muted body */
  --sl-color-gray-5: oklch(35% 0.02 240); /* borders */

  /* Accent = mint/teal */
  --sl-color-accent-low: oklch(35% 0.09 180); /* dark mint for chips/cards */
  --sl-color-accent: oklch(70% 0.15 180); /* primary brand mint */
  --sl-color-accent-high: oklch(87% 0.06 180); /* tints for hovers */

  /* Shape & rhythm */
  --sl-border-radius: 12px;
  --sl-content-width: 72rem; /* wider reading column */
}
```

Wire it up in `astro.config.mjs`:

```js
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

export default defineConfig({
  integrations: [
    starlight({
      title: "Hephaestus",
      customCss: ["./src/styles/theme.css"],
      sidebar: [{ label: "Docs", items: [{ slug: "index" }] }],
      useStarlightUiThemeColors: true,
    }),
  ],
});
```

---

### 2. Typography & Spacing

Import a clean grotesk (e.g., Inter) or your brand font, assign globally via Starlight’s custom fonts guide. Example for `theme.css`:

```css
:root {
  --sl-text-5xl: clamp(2.75rem, 6vw, 4.25rem);
}
body {
  font-feature-settings:
    "ss01",
    "ss02",
    "tnum" 1;
}
```

---

### 3. AQRisk-style Landing Page

Create `src/pages/index.astro` for a splash hero and card grid:

```astro
---
import { IconChevronRight } from 'lucide-astro/icons';
const cards = [
    { title: 'Banking Optimization', href: '/docs/tutorials/', k: 'Increase profitability' },
    { title: 'OpRisk Excellence', href: '/docs/how-to/', k: 'Reduce loss' },
    { title: 'Specialist Analytics', href: '/docs/reference/', k: 'Scale decisions' },
];
---

<section class="hero">
    <h1>Boost profitable growth<br/>with next-level optimization</h1>
    <p class="lede">Set your data free with proven solutions and supercharge value-creation.</p>
    <a class="cta" href="/docs/get-started/">See solutions <IconChevronRight/></a>
</section>

<section class="grid">
    {cards.map(c => (
        <a class="card" href={c.href}>
            <h3>{c.title}</h3><p>{c.k}</p>
        </a>
    ))}
</section>

<style>
.hero { padding: 8rem 0 3rem; }
.hero h1 { line-height: 1.05; margin: 0 0 1rem; }
.hero .lede { color: var(--sl-color-gray-6); max-width: 48ch; }
.cta { display:inline-flex; gap:.5rem; align-items:center; padding:.9rem 1.1rem;
    border-radius:12px; background: var(--sl-color-accent); color: black; font-weight:600; }
.grid { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 1rem; margin-top: 2rem; }
.card { padding:1.25rem; border:1px solid var(--sl-color-gray-5); border-radius:12px; background:
    color-mix(in oklch, var(--sl-color-bg) 90%, var(--sl-color-accent-low) 10%); }
.card:hover { border-color: var(--sl-color-accent); transform: translateY(-2px); transition:.2s; }
@media (max-width: 960px){ .grid{ grid-template-columns:1fr; } .hero{ padding:5rem 0 2rem;}}
</style>
```

---

### 4. Testimonials Everywhere

Model client quotes as a content collection:

```ts
// src/content.config.ts
import { defineCollection, z } from "astro:content";
export const collections = {
  testimonials: defineCollection({
    type: "data",
    schema: z.object({
      name: z.string(),
      role: z.string(),
      org: z.string(),
      quote: z.string(),
      avatar: z.string().optional(),
    }),
  }),
};
```

Component to display testimonials:

```astro
---
// src/components/Testimonials.astro
import { getCollection } from 'astro:content';
const quotes = await getCollection('testimonials');
---

<ul class="tlist">
    {quotes.map(q => <li><blockquote>“{q.data.quote}”</blockquote>
        <div class="meta">{q.data.name} — {q.data.role}, {q.data.org}</div></li>)}
</ul>
<style>
.tlist{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(22rem,1fr))}
blockquote{font-size:1.05rem;color:var(--sl-color-text);border-left:3px solid var(--sl-color-accent);padding-left:.9rem}
.meta{color:var(--sl-color-gray-6)}
</style>
```

Override a Starlight slot (e.g., sidebar/footer) to sprinkle testimonials site-wide.

---

### 5. “Solution Features” as Accordions

Use HTML `<details>` / `<summary>` for expandable sections, styled via your CSS.

---

### 6. Header and Primary CTA

Override the Header component or inject a right-aligned slot for a branded CTA:

```astro
<!-- src/components/HeaderCta.astro -->
<a href="/contact/" class="cta">Get in touch</a>
<style>
.cta{padding:.55rem .9rem;border-radius:10px;font-weight:600;
 background:var(--sl-color-accent); color:black; border:1px solid transparent}
.cta:hover{border-color:var(--sl-color-accent-high)}
</style>
```

---

### 7. Code Blocks That Match the Brand

Keep `useStarlightUiThemeColors: true` so code UI matches your palette.

---

### 8. Theme Mode Policy

Lock Starlight to dark-only and hide the selector if you want a dark-led experience.

---

### 9. Ship It on GitHub Pages

Use Astro’s official Pages workflow for deployment.

---

## Quick Config Example

```ts
// starlight.config.ts
import { defineConfig } from "@astrojs/starlight/config";
export default defineConfig({
  title: "Hephaestus",
  logo: { src: "/assets/logo.svg", replacesTitle: true },
  social: { github: "https://github.com/IAmJonoBo/Hephaestus" },
  sidebar: [
    { label: "Tutorials", link: "/docs/tutorials/" },
    { label: "How-to", link: "/docs/how-to/" },
    { label: "Reference", link: "/docs/reference/" },
    { label: "Explanation", link: "/docs/explanation/" },
  ],
  components: {
    // 'Header:Right': './src/components/HeaderCta.astro',
    // 'Page:Footer': './src/components/Testimonials.astro',
  },
  useStarlightUiThemeColors: true,
});
```

---

## Sanity Check

If your current site is MkDocs-based, migrate IA as-is and apply the landing + tokens first for immediate improvement.

---

## Why This Matches AQRisk—Without Cloning

- **Structure parity:** Hero → value drivers → solutions → quotes.
- **Palette & tone:** Dark canvas + mint accent for “Nordic fintech” clarity.
- **Reusable social proof:** Quotes as a collection, surfaced wherever needed.

---

## Provenance

- **Data:** AQRisk home/solution pages, quotes taxonomy, Starlight docs, Astro content collections, GitHub Pages deploy.
- **Methods:** Visual audit → extract patterns → map to Starlight primitives.
- **References:** AQRisk UI, Starlight guides, Astro deploy workflow.

---

_If you want a one-shot PR (theme tokens, hero, testimonials, header CTA), just ask!_
