# Changelog

All notable changes to IssueSuite are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (Unreleased)

- `issuesuite init` scaffolds starter configs, specs, VS Code tasks, CI workflow, and gitignore entries with optional extras (`--include`, `--all-extras`).
- `issuesuite upgrade` surfaces configuration recommendations (e.g. telemetry defaults, mapping file migration) with optional JSON output for automation.
- New runtime helpers (`runtime.py`) instrument every CLI command with plugin callbacks and telemetry events.
- Opt-in telemetry sink (`telemetry.py`) and pluggable extension system (`plugins.py`) with entry-point and environment discovery.
- Bootstrap utilities and templates (`scaffold.py`, `issuesuite.bootstrap`, `scripts/issuesuite-preflight.sh`, `scripts/issuesuite-dx-sweep.sh`) streamline onboarding and local automation.

### Changed (Unreleased)

- CLI refactored to delegate config preparation and execution orchestration to runtime helpers, reducing command duplication.
- Documentation reorganized into a Diátaxis structure (`docs/tutorials/`, `docs/how-to/`, `docs/reference/`, `docs/explanations/`) with refreshed guides and navigation.
- README quick start expanded with scaffolding workflow, observability guidance, and links to the new documentation layout.
- Packaging and developer tooling scripts updated to align with the scaffolding workflow and observability features.

### Fixed (Unreleased)

- VS Code task setup now deduplicates entries when merging with existing `tasks.json` during bootstrap.

## [0.1.10] - 2025-09-26

## [0.1.11] - 2025-09-26

### Added (0.1.11)

- New `agent-apply` CLI subcommand to ingest agent/Copilot completion updates (JSON), update `ISSUES.md` (status + append completion summaries), optionally update docs, and run a follow-up sync.
- Shared rendering helpers in `parser.py` (`render_yaml_block_from_fields`, `render_issue_block`) to ensure canonical formatting across import/agent-apply and future renderers.

### Changed (0.1.11)

- `import` and `agent-apply` now use the central renderer utilities for consistent YAML/Markdown output.
- Default agent-apply behavior respects status (closed issues get closed) and performs a dry-run sync unless `--apply` is provided; flags support explicit overrides.

### Fixed (0.1.11)

- Tests added to assert ISSUES.md is actually modified by agent-apply (status closed + completion summary) and that labels/milestone are preserved; full suite remains green.
- Documentation updates in README and VS Code setup to describe agent-apply usage and workflows.

### Changed (0.1.10)

- Bump version for docs/tasks/workflow updates and minor polish since 0.1.9.

### Fixed (0.1.10)

- Minor documentation nits and VS Code tasks deduplication.

## [0.1.9] - 2025-09-26

### Changed (0.1.9)

- Publish workflow aligned with PyPI Trusted Publishers (single job, job-level id-token; optional TestPyPI toggle).
- Removed job-level environment claim to simplify OIDC matching.
- Comprehensive documentation overhaul: README, PACKAGING (Trusted Publishers), VS Code setup, mapping design.

### Fixed (0.1.9)

- Addressed publishing failures by ensuring correct OIDC permissions and reducing claim mismatches.

## [0.1.8] - 2025-09-26

### Fixed (0.1.8)

- Eliminated recursion/stall in concurrent sync path by switching to explicit sequential fallback when an event loop is active.
- Isolated project v2 “real mode” tests to bypass session-wide mock, restoring expected behavior for CLI calls.

### Internal (0.1.8)

- Ruff lint improvements: import order cleanups, mypy-friendly type tweaks, and per-file test ignores for non-critical rules.
- Minor concurrency polish: async-safe subprocess usage fallback, typed helpers, and constants for worker thresholds.

## [0.1.7] - 2025-09-26

### Added (0.1.7)

- AI mode via `ISSUESUITE_AI_MODE=1` forcing dry-run safety for all sync/summary/export operations.
- `ai-context` CLI command producing structured JSON (spec preview, config hints, env flags, recommendations) for AI assistant ingestion.
- Test coverage for AI mode enforcement and ai-context export.
- Pre-commit configuration with Ruff (autofix), mypy, fast pytest subset.
- Quiet mode flag `--quiet` and `ISSUESUITE_QUIET=1` environment variable to suppress incidental logging for clean JSON piping.
- Enriched sync summary metadata: `mapping_present`, `mapping_size`, optional `mapping_snapshot` (small mappings) exposing index state for future reconcile/import features.
- `ai-context` mapping enrichment fields: `mapping.present`, `mapping.size`, `mapping.snapshot_included`, conditional `mapping.snapshot`.
- Deterministic issue spec slug markers `<!-- issuesuite:slug=<slug> -->` auto-inserted for idempotent parsing.
- Strict parser for new canonical spec format (slug heading + fenced YAML) with comprehensive edge‑case tests.
- JSON Schema for AI context (`ai_context.schema.json`) with CLI emission and library access via `issuesuite.schemas.get_schemas()`.
- Programmatic `get_ai_context(cfg, preview=...)` API returning structured AI context document.
- Optional milestone enforcement (`milestone_required` config flag) ensuring every spec declares a milestone (default off for backward compatibility).
- Centralized retry abstraction (`issuesuite.retry.run_with_retries`) for GitHub CLI transient errors (rate limit / abuse / secondary rate limit) with env overrides `ISSUESUITE_RETRY_ATTEMPTS`, `ISSUESUITE_RETRY_BASE`.
- Dedicated retry unit tests covering transient success path, non-transient immediate failure, and transient exhaustion.
- Error taxonomy & redaction scaffold (`errors.py`) with `classify_error` and `redact` helpers.
- Structured sync failure logging enriched with error classification metadata (category, transient, original_type).
- AI context document now includes `errors` section (categories + retry strategy/overrides).
- Config option `schema_ai_context_file` under `ai:` to customize emitted AI context schema filename.
- Tests for programmatic AI context structure and schema emission.

### Changed (0.1.7)

- Ruff configuration with per-file complexity ignore for CLI dispatcher (`PLR0915`).
- Refactored `setup` subcommand into smaller helper functions reducing complexity.
- Hard migration to canonical spec format: `## [slug: <id>]` followed by fenced `yaml` block; legacy numbered heading format removed (now raises error with actionable guidance).

### Internal (0.1.7)

- README updated with AI integration guidance and sample `ai-context` output.
- Added per-file ignore instead of further refactor to keep CLI command registration explicit.
- Added context manager `_QuietLogs` for suppressing logger output when quiet mode enabled.
- Set `milestone_required` default to `false` to avoid unexpected failures in existing configurations.
- Integrated classification in `core.IssueSuite.sync` error path.
- Added helper utilities `_load_index_mapping`, `_truncate_body_diffs`, `_iter_updated_entries` to reduce orchestrator complexity and prepare for reconcile logic.

## [0.1.6] - 2025-09-26

### Added (0.1.6)

- Project v2 integration groundwork: persistent project/field cache with TTL + disable flag.
- Single-select option name → ID mapping (case-insensitive) in project field updates.
- Tests: caching reuse, option mapping (case-insensitive), restored `_get_issue_id` behavior.

### Changed (0.1.6)

- Refactored project assigner to smaller helpers (`_apply_field_mappings`).
- Consolidated duplicate / corrupted `project.py` after refactor attempts.

### Fixed (0.1.6)

## Contributing to the Changelog

When contributing changes, please follow these guidelines:

1. **Add entries to [Unreleased]** section during development
2. **Use standard categories**: Added, Changed, Deprecated, Removed, Fixed, Security
3. **Write clear, descriptive entries** that explain the impact to users
4. **Link to relevant issues/PRs** where appropriate
5. **Move items to versioned section** when releasing

### Entry Format

```markdown
### Added

- New feature description with impact explanation [#123](link-to-issue)

### Changed

- Changed feature description explaining what and why [#456](link-to-pr)

### Fixed

- Bug fix description with impact [#789](link-to-issue)
```

### Version Numbering

IssueSuite follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

Examples:

- `0.1.0 → 0.1.1`: Bug fixes only
- `0.1.1 → 0.2.0`: New features, backwards compatible
- `0.2.0 → 1.0.0`: Breaking API changes or major milestone

---

For detailed technical changes, see:

- [GitHub Releases](https://github.com/IAmJonoBo/IssueSuite/releases)
- [Commit History](https://github.com/IAmJonoBo/IssueSuite/commits/main)
- [Pull Requests](https://github.com/IAmJonoBo/IssueSuite/pulls?q=is%3Apr+is%3Aclosed)
