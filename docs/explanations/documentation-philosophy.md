# Documentation Philosophy

IssueSuite follows the [Diátaxis](https://diataxis.fr/) framework to keep documentation purposeful and scannable.

## Goals

- Provide a frictionless "Hello IssueSuite" journey with a single tutorial.
- Separate day-to-day developer workflows from maintainer automation.
- Offer authoritative reference material for CLI commands and configuration keys.
- Capture design intent for long-lived architectural decisions.

## Structure

| Category | Location | Purpose |
| --- | --- | --- |
| Tutorials | `docs/tutorials/` | Guided learning experiences for newcomers |
| How-to guides | `docs/how-to/` | Task-oriented instructions for practitioners |
| Reference | `docs/reference/` | Authoritative, factual resources (CLI, configuration) |
| Explanations | `docs/explanations/` | Architectural context, design docs, and philosophy |

## Maintenance tips

- Keep tutorials linear—each step should build on the previous one without branching.
- When documenting a new feature, start with a how-to if the workflow is user-facing, then add reference entries for new configuration fields.
- Design decisions, trade-offs, or roadmap notes belong in explanations.
- Update cross-links from the README whenever new documents are added so readers can find them quickly.

The prior `docs/documentation_plan.md` file has been retired in favor of this living philosophy document.
