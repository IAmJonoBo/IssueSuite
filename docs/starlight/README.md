# IssueSuite Starlight Workspace

This directory hosts the Astro Starlight site that publishes IssueSuite's documentation. Key commands:

```bash
npm install
npm run check
npm run build
# or
nox -s docs
```

The site is organized using the Diátaxis framework under `src/content/docs` with the following collections:

- `tutorials/`
- `how-to/`
- `reference/`
- `explanations/`

Architecture decision records live in `../adrs` and are tracked via `docs/adrs/index.json`. Regression tests in `tests/test_documentation_structure.py` ensure pages include frontmatter and ADR metadata stays in sync.
