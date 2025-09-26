# Copilot Instructions for IssueSuite

IssueSuite declaratively manages GitHub Issues from a single `ISSUES.md` file using stable slugs, fenced YAML blocks, deterministic hashes, and readable diffs. Core code lives under `src/issuesuite/`.

## Architecture and Flow
- CLI (`src/issuesuite/cli.py`) parses args and subcommands: `validate`, `sync`, `export`, `summary`, `schema`, `reconcile`, `ai-context`.
- Orchestrator (`src/issuesuite/orchestrator.py`) wraps core sync to emit an enriched summary, prune/persist mapping, and apply diff truncation.
- Core (`src/issuesuite/core.py`) parses specs, computes a plan, and performs create/update/close against GitHub (or mock mode). Returns structured summary incl. `plan` when dry-run.
- Parser (`src/issuesuite/parser.py`) enforces the spec format below; raises explicit parse errors.
- GitHub integration (`src/issuesuite/github_issues.py`) performs operations with centralized retry (`src/issuesuite/retry.py`).
- Project (v2) integration (`src/issuesuite/project.py`) adds optional Project assignment with lightweight on-disk caching in `.issuesuite_cache/`.
- Schemas and AI context: `src/issuesuite/schemas.py` and `src/issuesuite/ai_context.py` expose JSON Schemas and a machine-readable context document.

## Source of Truth: ISSUES.md format
Each issue is a level-2 heading with a slug plus an immediate fenced YAML block:

```markdown
## [slug: api-timeouts]

```yaml
title: Investigate API timeouts
labels: [bug, backend]
milestone: Sprint 1
body: |
	Requests intermittently exceed 5s …
```
```

Slugs must match `^[a-z0-9][a-z0-9-_]*$` (configurable).

## Developer Workflows
- Validate: `issuesuite validate --config issue_suite.config.yaml`
- Safe dry-run sync (+ summary): `issuesuite sync --dry-run --update --config issue_suite.config.yaml --summary-json issues_summary.json`
- Export parsed specs: `issuesuite export --pretty --config issue_suite.config.yaml --output issues_export.json`
- Human summary: `issuesuite summary --config issue_suite.config.yaml`
- Reconcile drift (read-only): `issuesuite reconcile --config issue_suite.config.yaml`
- AI context JSON: `issuesuite ai-context --quiet --config issue_suite.config.yaml > ai_context.json`
- Generate schemas: `issuesuite schema --config issue_suite.config.yaml`

VS Code tasks exist for these (see workspace Tasks: Validate, Dry-run Sync, Full Sync, Export, Summary, Generate Schemas).

## Modes, Config, and Artifacts
- Config (`issue_suite.config.yaml`) controls `dry_run_default`, `truncate_body_diff`, patterns, and output paths (`issues_summary.json`, `issues_export.json`, `.issuesuite_mapping.json`, `.issuesuite_hashes.json`).
- Mapping is also persisted to `.issuesuite/index.json` by the orchestrator; stale slugs are pruned on non-dry-run syncs.
- Env flags: `ISSUESUITE_AI_MODE=1` (force dry-run), `ISSUES_SUITE_MOCK=1` (offline; no GitHub calls), `ISSUESUITE_QUIET=1` (suppress logs), `ISSUESUITE_DEBUG=1` (verbose), retry tuning (`ISSUESUITE_RETRY_ATTEMPTS`, `ISSUESUITE_RETRY_BASE`, optional `ISSUESUITE_RETRY_MAX_SLEEP`).
- Project cache env: `ISSUESUITE_PROJECT_CACHE_TTL` (default 3600s), `ISSUESUITE_PROJECT_CACHE_DISABLE=1`.
- Dry-run returns a `plan` array summarizing proposed actions; diffs are truncated to `truncate_body_diff` chars (default 80).

## Programmatic Usage
```python
from issuesuite import IssueSuite, load_config
cfg = load_config('issue_suite.config.yaml')
suite = IssueSuite(cfg)
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=False)
print(summary['totals'])
```
Or use the orchestrator helper `sync_with_summary` for enriched summary + mapping persistence.

## Pointers and Conventions
- Idempotency: external ID = slug; mapping maintained across runs; updates are hash-driven.
- Tests live in `tests/` (see `test_mock_mode.py`, `test_cli_basic.py`, etc.); use mock mode for offline runs.
- Key modules: CLI (`cli.py`), core (`core.py`), orchestrator (`orchestrator.py`), parser (`parser.py`), retry (`retry.py`), GitHub ops (`github_issues.py`), Project v2 (`project.py`).

Questions or gaps? Tell us which section is unclear (format rules, mapping behavior, project integration, retries), and we’ll tighten these instructions.

## Useful CLI flags and CI drift gating
- `--apply` is an alias for `--update` (perform mutations when not dry-run).
- `--plan-json <file>` (with `--dry-run`) writes only the planned actions to a JSON file.
- Reconcile exit codes: `0` (in sync), `2` (drift detected), `>0` (errors). Use in CI to fail on drift.

## Testing quickstart
- Offline/fast tests via mock mode: set `ISSUES_SUITE_MOCK=1` when invoking commands in tests.
- Focus areas: parser edge cases (`test_parser_edge_cases.py`), mapping persistence (`test_mapping_persistence.py`), orchestrator pruning (`test_mapping_stale_prune.py`), project integration (`test_project_*`).
- Run test suite from repo root with Python 3.11+ (see `pyproject.toml` for deps). If needed, install editable: `python -m pip install -e .[dev]`.

## Performance and concurrency
- Optional benchmarking emits `performance_report.json` when enabled in config (`performance.benchmarking: true`).
- Concurrency controls (default disabled) in config under `concurrency:` with `enabled` and `max_workers`.

## Agent quickstart
- Read-only preview: `ISSUESUITE_AI_MODE=1 issuesuite sync --dry-run --update --config issue_suite.config.yaml --summary-json issues_summary.json`
- Fully offline: `ISSUESUITE_AI_MODE=1 ISSUES_SUITE_MOCK=1 issuesuite summary --config issue_suite.config.yaml`
- Export specs: `issuesuite export --pretty --config issue_suite.config.yaml --output issues_export.json`

## Gotchas
- Spec format is strict: heading `## [slug: ...]` followed by fenced YAML. Parser errors are explicit; fix the spec rather than working around it.
- Non-dry-run writes mapping to `.issuesuite/index.json` and prunes stale slugs. Dry-run doesn’t persist.
- Body diffs are truncated per config; for full body comparison, inspect raw spec and live issue if needed.
- Retry/backoff is centralized; tune with `ISSUESUITE_RETRY_*` envs rather than adding ad-hoc sleeps.
- When assigning Projects (v2), option IDs are cached in `.issuesuite_cache/`; disable with `ISSUESUITE_PROJECT_CACHE_DISABLE=1`.

## GitHub App auth (optional)
- YAML keys (under `github.app` in `issue_suite.config.yaml`): `enabled`, `app_id`, `private_key_path`, `installation_id`.
- Values can reference env vars by using `$VARNAME`; loader resolves them (see `config.py`).
- Token is cached to `.github_app_token.json` with `0600` perms; in mock mode a placeholder token is used.

## Dry-run plan snapshot
When `--dry-run` is used, the summary includes a `plan` array like:

```jsonc
{
	"plan": [
		{
			"external_id": "api-timeouts",
			"action": "update", // create | update | close | skip
			"number": 1234,
			"changes": {"labels_added": 1, "labels_removed": 0, "milestone_changed": false, "body_changed": true}
		}
	]
}
```
On non-dry-run syncs, the merged slug→issue mapping is written to `.issuesuite/index.json` and stale slugs are pruned.

## Parse error quick fixes
- "Legacy numeric issue format detected" → Convert to slug + YAML format (see example above).
- "YAML for slug <slug> must be a mapping" → Ensure fenced YAML parses to a dict; keys like `title`, `labels`, `milestone`, `body`.
- "Missing fenced YAML after slug header" → Add a fenced block immediately after `## [slug: ...]` (allow blank lines only).
- Slug must match `^[a-z0-9][a-z0-9-_]*$` → rename to lowercase alnum, `-` or `_`.

## CI drift gate (example)
```bash
issuesuite reconcile --config issue_suite.config.yaml
status=$?
if [ "$status" -eq 2 ]; then
	echo "Roadmap drift detected (reconcile). Failing CI." >&2
	exit 2
elif [ "$status" -ne 0 ]; then
	echo "Reconcile error ($status)." >&2
	exit $status
fi
```

## Mapping snapshot threshold
- The orchestrator includes a full `mapping_snapshot` inline in enriched summaries when size ≤ 500.
- Snapshot source is `.issuesuite/index.json`; dry-run previews do not persist mapping.
