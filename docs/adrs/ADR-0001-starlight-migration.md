---
id: ADR-0001
title: Adopt Astro Starlight for documentation
status: Accepted
decision_date: 2025-10-09
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite's Markdown-only documentation made cross-linking and quality enforcement difficult. We needed a static site generator that embraced the Diátaxis framework, supported automated builds, and integrated with existing governance tooling.

## Decision

Adopt Astro Starlight as the documentation platform and restructure content into Diátaxis collections (`tutorials`, `how-to`, `reference`, `explanations`). Starlight's built-in navigation, search, and frontmatter validation pair well with our requirement for automated checks.

## Consequences

- Documentation lives in `docs/starlight` with npm scripts for check/build workflows.
- A new `nox -s docs` session executes `npm run check` and `npm run build`.
- Tests enforce frontmatter completeness and ADR index synchronisation.

## Follow-up work

- Publish preview builds per PR and host the site on GitHub Pages.
- Extend the ADR registry when new architectural decisions are made (e.g., documentation deployments, schema automation).
- Surface documentation health metrics in GitHub Projects dashboards.
