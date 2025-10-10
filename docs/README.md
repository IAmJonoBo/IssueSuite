# IssueSuite Documentation

> **Note**
> The canonical documentation lives in the [Astro Starlight workspace](starlight). The legacy Markdown tree has been retired to avoid divergence—browse the Starlight content directly when editing docs or run `nox -s docs` to build the site locally.

## Quick Links

Key entry points inside the workspace (run `scripts/refresh-deps.sh` or `nox -s lock`
after Renovate/Dependabot updates to keep lockfiles in sync):

- Tutorials: `docs/starlight/src/content/docs/tutorials/`
- How-to guides: `docs/starlight/src/content/docs/how-to/`
- Reference: `docs/starlight/src/content/docs/reference/`
- Explanations: `docs/starlight/src/content/docs/explanations/`

Refer to `docs/adrs/index.json` for tracked decisions and keep `Next_Steps.md` updated with documentation milestones.

## Quality Standards

Every documentation page must meet these standards:

- ✅ **Frontmatter complete**: `title`, `description`, and `template` fields present
- ✅ **Diátaxis category**: Correctly categorized as tutorial, how-to, reference, or explanation
- ✅ **Build passes**: `npm run check` and `npm run build` succeed without errors
- ✅ **Links validated**: All internal and external links resolve correctly
- ✅ **SEO optimized**: Descriptive titles and meta descriptions for search engines
- ✅ **Accessible**: Proper heading hierarchy, alt text for images, semantic HTML

Run `nox -s docs` or `cd docs/starlight && npm run check` to validate documentation quality before committing changes.

## Archive

Legacy and completed documentation (gap analyses, implementation summaries, internal communications) has been moved to [docs/archive/](archive/) to keep the active documentation focused on current, actionable content for users and contributors.
