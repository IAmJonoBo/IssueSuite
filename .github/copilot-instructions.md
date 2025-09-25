# Copilot Instructions for IssueSuite

## Project Overview
IssueSuite automates GitHub issue management using a declarative approach. The main source of truth is a Markdown file (`ISSUES.md`), which defines the roadmap. The tool syncs GitHub issues to match this file, using deterministic hashes and readable diffs. All core logic is in `src/issuesuite/`.

## Key Components
- **CLI Entrypoint:** `src/issuesuite/cli.py` — Handles command-line operations.
- **Config Loader:** `src/issuesuite/config.py` — Loads and validates YAML config (`issue_suite.config.yaml`).
- **Core Logic:** `src/issuesuite/core.py` — Main sync, diff, and export logic.
- **Orchestrator:** `src/issuesuite/orchestrator.py` — High-level sync and summary output.
- **Schemas:** `src/issuesuite/schemas.py` — JSON schema generation for exports and summaries.
- **Project Model:** `src/issuesuite/project.py` — Project-level abstractions.

## Developer Workflows
- **Install:** `pip install issuesuite`
- **Validate:** `issuesuite validate --config issue_suite.config.yaml`
- **Sync (dry-run):** `issuesuite sync --dry-run --update --config issue_suite.config.yaml --summary-json issues_summary.json`
- **Export:** `issuesuite export --pretty --config issue_suite.config.yaml --output issues_export.json`
- **Summary:** `issuesuite summary --config issue_suite.config.yaml`
- **Schema Generation:** `issuesuite schema --stdout`
- **Debug Logging:** Set `ISSUESUITE_DEBUG=1` for verbose logs.
- **Mock Mode:** Set `ISSUES_SUITE_MOCK=1` to suppress GitHub API calls for offline testing.

## Patterns & Conventions
- **Idempotency:** All sync operations use stable external IDs and content hashes for deterministic updates.
- **Configurable Patterns:** ID and milestone regex, global label injection, and feature flags are set in `issue_suite.config.yaml`.
- **Diff Truncation:** Body diffs are truncated to 80 chars by default (configurable).
- **JSON Artifacts:** Exports and summaries are written as `issues_export.json` and `issues_summary.json`.
- **Schema Versioning:** JSON schemas for exports and summaries are versioned and can be generated via CLI or library.

## Testing
- **Unit tests:** Located in `tests/` (e.g., `test_cli_basic.py`, `test_mock_mode.py`).
- **Mock Mode:** Use `ISSUES_SUITE_MOCK=1` for offline test runs.

## Integration Points
- **GitHub API:** All real syncs interact with GitHub via CLI or API (suppressed in mock mode).
- **Markdown Roadmap:** The `ISSUES.md` file is the canonical source for issues.
- **Config File:** `issue_suite.config.yaml` controls patterns, labels, milestones, and feature flags.

## Example Usage
```python
from issuesuite import IssueSuite, load_config
cfg = load_config('issue_suite.config.yaml')
suite = IssueSuite(cfg)
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=False)
print(summary['totals'])
```

## References
- `README.md` — Quick start, config, and usage examples
- `src/issuesuite/` — All core logic and helpers
- `tests/` — Unit tests and mock mode examples

---

If any section is unclear or missing, please provide feedback to improve these instructions.