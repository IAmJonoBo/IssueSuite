# IssueSuite

[![PyPI Version](https://img.shields.io/pypi/v/issuesuite.svg)](https://pypi.org/project/issuesuite/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/IAmJonoBo/IssueSuite)
[![Python Versions](https://img.shields.io/pypi/pyversions/issuesuite.svg)](https://pypi.org/project/issuesuite/)
[![CI](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/ci.yml/badge.svg)](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/ci.yml)

Declarative GitHub Issues automation — manage a roadmap from a single `ISSUES.md` file (using **slug headings + fenced YAML blocks**) and keep real GitHub issues perfectly in sync (create / update / close) with deterministic hashes, readable diffs, JSON artifacts, and optional preflight resource creation.

## Features

- Single source of truth in Markdown (`ISSUES.md`), each item. Example:

  ```markdown
  ## [slug: api-timeouts]
  ```

  ```yaml
  title: Investigate API timeouts
  labels: [bug, backend]
  milestone: Sprint 1
  body: |
    Requests intermittently exceed 5s …
  ```

  The parser requires this exact pattern: a level-2 heading with `[slug: <slug>]` followed immediately (allowing blank lines) by a fenced yaml block.

- Idempotent create/update/close using stable external IDs & content hashes
- Human & machine-readable diffs (labels, milestone, body snippet)
- JSON export (`issues_export.json`) + change summary (`issues_summary.json`)
- JSON Schemas for export/summary and AI context
- Schema registry with explicit version metadata (`issuesuite.schema_registry`) to keep downstream consumers synchronized as artifacts evolve.
- Configurable patterns (ID regex, milestone naming, global injected labels)
- Optional preflight auto-create of labels & milestones (feature flags)
- AI tooling: generated JSON Schemas for export, change summary, and AI context (+ `issuesuite.schemas.get_schemas()`)
- AI mode (safety): `ISSUESUITE_AI_MODE=1` forces all syncs into dry-run (no mutations) even if `--dry-run` omitted
- AI context export: `issuesuite ai-context` emits structured JSON (preview of spec, config hints, env suggestions) for assistant ingestion
- Agent updates: `issuesuite agent-apply` ingests AI/agent completion summaries and updates `ISSUES.md` (and optional docs) before syncing
- Quiet mode: `--quiet` or `ISSUESUITE_QUIET=1` suppresses informational logging (helpful when piping JSON to other tools)
- Offline-ready dependency governance via `issuesuite.dependency_audit` with pip-audit integration and curated advisories for air-gapped runners
- Resilient `pip-audit` wrapper and `issuesuite security` command merging curated offline advisories with live vulnerability feeds when available; tune the watchdog via `ISSUESUITE_PIP_AUDIT_TIMEOUT` to cap remote hangs
- Automated offline advisory refresh via `python -m issuesuite.advisory_refresh --refresh --check` and the CLI flag `issuesuite security --refresh-offline`
- Telemetry breadcrumbs when resilient pip-audit falls back to offline advisories so operators can observe degraded remote feeds
- Deterministic changelog updates with `scripts/update_changelog.py` (non-blocking lock) and `nox` developer sessions mirroring CI gates
- Debug logging via `ISSUESUITE_DEBUG=1`
- Mock mode (`ISSUES_SUITE_MOCK=1`) for offline tests w/out GitHub API
  - In mock mode all GitHub CLI calls are suppressed (even without `--dry-run`) and operations are printed as `MOCK <action>`.
  - Mock create operations fabricate deterministic incremental issue numbers so mapping persistence and tests remain stable.
  - Dry-run planning: `issuesuite sync --dry-run` now returns a `plan` array in the summary showing proposed actions (`create|update|close|skip`) with label/milestone/body change counts.
  - Plan artifacts: the CLI honours `--plan-json <file>` (or the config `output.plan_json`, default `issues_plan.json`) to write just the plan to disk for CI review.
- Pluggable extensions and telemetry: configure `extensions` and `telemetry` blocks (or use `ISSUESUITE_PLUGINS` / `ISSUESUITE_TELEMETRY`) to emit structured events and trigger entry-point hooks after every CLI command. See [Extensions, Plugins, and Telemetry](docs/explanations/extensions.md) for setup details.

## Quick Start

1. **Install the CLI (pipx recommended)**

```bash
pipx install issuesuite
# or: pip install issuesuite
```

1. **Scaffold a ready-to-run workspace**

```bash
issuesuite init --all-extras
```

This creates `issue_suite.config.yaml`, a starter `ISSUES.md`, `.vscode` tasks, a CI workflow, and a `.gitignore` snippet. Re-run with `--force` to regenerate.

1. **Run the preflight bundle**

```bash
./scripts/issuesuite-preflight.sh
```

The script validates specs and performs a dry-run sync, publishing `issues_summary.json` and `issues_plan.json` for inspection. Prefer the VS Code task **IssueSuite: Preflight** for one-click runs.

1. **Promote to full sync when ready**

```bash
issuesuite sync --update --config issue_suite.config.yaml --summary-json issues_summary.json
```

Add the `--preflight` flag (or set `behavior.dry_run_default: true`) to auto-create labels/milestones before closing the dry-run loop.

See the [Getting Started tutorial](docs/tutorials/getting-started.md) for a narrated walkthrough, including troubleshooting tips and screenshots.

Handy follow-up commands:

```bash
# Emit schemas to default files
issuesuite schema --config issue_suite.config.yaml

# Offline dependency audit with resilient pip-audit fallback
issuesuite security --offline-only
issuesuite security --pip-audit --pip-audit-arg --format --pip-audit-arg json
```

### Developer Tooling

Run the consolidated quality gates locally with the bundled `nox` sessions:

```bash
nox -s tests lint typecheck security secrets build
```

Frontier Apex prototypes introduce two new harnesses you can run ad-hoc while we
stabilise the elevated standards:

```bash
# Emit strict mypy telemetry without failing the workflow
python scripts/type_coverage_report.py

# Validate CLI help ergonomics across critical subcommands
python scripts/ux_acceptance.py

# Export coverage history for GitHub Projects dashboards
python scripts/coverage_trends.py
```

Enable the repo-managed pre-commit hook so commits automatically use the local
virtualenv without manual activation:

```bash
git config core.hooksPath .githooks
```

This looks for `.venv` (or `venv` / `.env`) under the repository root before
falling back to a globally installed `pre-commit`.

When preparing release notes, use `scripts/update_changelog.py` to append a new entry without risking editor hangs caused by blocking file locks:

```bash
python scripts/update_changelog.py 0.1.12 \
  --highlight "Document schema registry and changelog guard" \
  --highlight "Ship developer nox sessions"
```

### Learn more

- Tutorials: [Getting started](docs/tutorials/getting-started.md)
- How-to guides: [CI/CD](docs/how-to/ci-cd.md), [Homebrew automation](docs/how-to/homebrew.md), [VS Code tasks](docs/how-to/vs-code.md)
- Reference: [CLI commands](docs/reference/cli.md), [Configuration schema](docs/reference/configuration.md)
- Explanations: [Architecture overview](docs/explanations/architecture.md), [Plugins & telemetry](docs/explanations/extensions.md)
- Observability quick start: run `issuesuite upgrade --json` to see recommended configuration defaults and add a `telemetry` block, e.g.

  ```yaml
  telemetry:
    enabled: true
    store_path: .issuesuite/telemetry.jsonl
  extensions:
    enabled: true
    disabled: []
  ```

  With telemetry enabled you can tail `telemetry.jsonl` to monitor command usage, while entry-point or environment-defined plugins receive the same payload for custom workflows.

### Authentication quick check

Run `issuesuite setup --check-auth` to ensure your GitHub token or GitHub App credentials are detected before attempting a full sync. Need a starter `.env`? Generate one with `issuesuite setup --create-env`, then paste your `GITHUB_TOKEN` (and optional GitHub App values) before running the tasks above.

### Guided setup tour

Prefer a narrative walkthrough? `issuesuite setup --guided` inspects your workspace, highlights missing assets (config, specs, coverage telemetry), and prints recommended commands (init, quality gates, coverage trend export) in an ANSI-friendly checklist. Run it any time you need to confirm the repository is Frontier-ready.

### Agent Apply (update ISSUES.md from agent output)

Use agent-apply to let an agent (e.g., Copilot) mark items complete and append summaries in `ISSUES.md`, then optionally run a sync.
You can trigger this via VS Code tasks: "IssueSuite: Agent Apply (dry-run)" or "IssueSuite: Agent Apply (apply)".

Basics:

```bash
# Dry-run sync by default after applying file updates
issuesuite agent-apply --config issue_suite.config.yaml --updates-json updates.json

# Apply changes to GitHub too (sets --update)
issuesuite agent-apply --config issue_suite.config.yaml --updates-json updates.json --apply

# Skip the sync step entirely (only updates local files)
issuesuite agent-apply --config issue_suite.config.yaml --updates-json updates.json --no-sync
```

Accepted JSON shapes for updates.json (a starter example lives at `agent_updates.json`):

- List of updates:

  ```jsonc
  [
    {
      "slug": "api-timeouts",
      "completed": true,
      "summary": "Fixed retry jitter; added metrics.",
    },
  ]
  ```

- Object with `updates` array:

  ```jsonc
  {
    "updates": [
      {
        "external_id": "api-timeouts",
        "status": "closed",
        "comment": "Released v1.2.",
      },
    ],
  }
  ```

- Mapping of slug → update object:

  ```jsonc
  {
    "perf-tuning": { "completed": true, "summary": "Profiling + batch writes" },
  }
  ```

Flags and defaults:

- `--apply` performs real GitHub mutations during the sync; otherwise the sync is dry-run
- `--no-sync` avoids running sync after file updates
- `--respect-status/--no-respect-status` controls whether closed specs trigger issue closure (default true)
- `--dry-run-sync/--no-dry-run-sync` explicitly forces dry-run or not when combined with `--apply`
- `--summary-json` writes the sync’s summary to a path (the VS Code tasks write to `issues_summary.json`)

Notes:

- agent-apply uses the same parser and a shared renderer as other commands to keep formatting consistent
- When `completed` is true (or `status: closed`) a dated “Completion summary (YYYY-MM-DD)” section is appended to the body (marker ensured)
- Labels and milestone are preserved unless explicitly changed by the update

### Reconcile (Spec vs Live Drift Detection)

The `reconcile` command performs a read-only comparison between your canonical `ISSUES.md` specs and the current live GitHub issues (matching on the hidden slug marker and heuristic title fallback). It reports three drift categories:

- `spec_only`: Spec exists in `ISSUES.md` but no matching live issue (potentially needs creation)
- `live_only`: Live issue managed by IssueSuite (marker present) but missing from specs (potentially should be closed or resurrected)
- `diff`: Both exist but labels / milestone / title / body differ (contains a concise diff)

Usage:

```bash
issuesuite reconcile --config issue_suite.config.yaml
```

Exit codes:

| Code         | Meaning                                                           |
| ------------ | ----------------------------------------------------------------- |
| `0`          | In sync (no drift)                                                |
| `2`          | Drift detected (one or more spec_only / live_only / diff entries) |
| `>0` (other) | Operational error (parse failure, config error, etc.)             |

Sample JSON (abbreviated):

```jsonc
{
  "in_sync": false,
  "spec_count": 12,
  "live_count": 11,
  "drift": {
    "spec_only": ["new-endpoint-hardening"],
    "live_only": ["deprecated-cleanup-task"],
    "diff": [
      {
        "slug": "api-timeouts",
        "changes": {
          "labels": { "added": ["priority:high"], "removed": [] },
          "milestone_changed": false,
          "body_changed": true,
        },
      },
    ],
  },
}
```

This allows CI pipelines to gate on drift (e.g., fail a PR if roadmap and issues diverge) without mutating any issues. Combine with `sync --dry-run` for deeper planned action insight.

### `--apply` Alias

For ergonomics, `issuesuite sync --apply` is equivalent to `--update` (perform mutations when not in dry-run). This mirrors common infra tooling conventions. You can still specify both; `--apply` just sets `update=True` internally.

## Configuration (`issue_suite.config.yaml`)

Key sections:

```yaml
version: 1
source:
  file: ISSUES.md
  # Default pattern now slug-based: lowercase alnum plus hyphen/underscore
  id_pattern: "^[a-z0-9][a-z0-9-_]*$"
  # Require every spec to declare a milestone (optional governance, default false)
  milestone_required: false
  milestone_pattern: "^(Sprint 0:|M[0-9]+:)"
defaults:
  inject_labels: [meta:roadmap, managed:declarative]
  ensure_milestones: ["Sprint 0: Mobilize & Baseline"]
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
behavior:
  truncate_body_diff: 80
output:
  summary_json: issues_summary.json
  plan_json: issues_plan.json
  export_json: issues_export.json
ai:
  schema_export_file: issue_export.schema.json
  schema_summary_file: issue_change_summary.schema.json
  schema_version: 1
```

## Library Usage

```python
from issuesuite import IssueSuite, load_config
cfg = load_config('issue_suite.config.yaml')
suite = IssueSuite(cfg)
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=False)
print(summary['totals'])
```

### Orchestrator (High-Level Sync)

For a one-call sync that also writes the mapping (future use) and enriched summary JSON with `schemaVersion`, timestamp, and `dry_run` flag, use the orchestrator helper:

```python
from issuesuite.config import load_config
from issuesuite.orchestrator import sync_with_summary

cfg = load_config('issue_suite.config.yaml')
summary = sync_with_summary(
  cfg,
  dry_run=True,
  update=True,
  respect_status=False,
  preflight=False,
  summary_path='issues_summary.json',
)
print(summary['totals'])
```

This mirrors the CLI `sync` output and applies diff body truncation according to `truncate_body_diff` in config.

### Dry-Run Plan Structure

When `dry_run=True` (or `--dry-run` via CLI) the returned summary includes:

```jsonc
"plan": [
  {
    "external_id": "api-timeouts",
    "title": "Investigate API timeouts",
    "action": "update",          // create | update | close | skip
    "number": 1234,               // existing issue number or null for create
    "labels": ["bug", "backend"],
    "milestone": "Sprint 1",
    "reason": "no existing match", // only set for create/skip rationales
    "changes": {                   // present for action=update
      "labels_added": 1,
      "labels_removed": 0,
      "milestone_changed": false,
      "body_changed": true
    }
  }
]
```

To export just the plan:

```bash
issuesuite sync --dry-run --update --plan-json plan.json --config issue_suite.config.yaml
```

### Mapping Persistence

Successful (non-dry-run) syncs persist a slug→issue number index at:

```text
.issuesuite/index.json
```

Format:

```json
{ "mapping": { "api-timeouts": 1234, "search-caching": 1235 } }
```

The enriched summary contains a snapshot (`mapping_snapshot`) when the mapping size is below a threshold (default 500). Stale slugs (removed from `ISSUES.md`) are pruned automatically on subsequent syncs.

Mock mode emits deterministic incremental numbers (starting at 1001+) enabling reliable mapping tests without contacting GitHub.

## JSON Schemas

Generate schemas (export + change summary + AI context):

CLI:

```bash
issuesuite schema --config issue_suite.config.yaml
```

Files written (defaults; configurable under `ai:` in config):

- `issue_export.schema.json`
- `issue_change_summary.schema.json`
- `ai_context.schema.json`

### Enriched Summary `last_error`

When a sync operation encounters an exception after partial processing, a structured
classification of the failure (`last_error`) is embedded into the enriched summary JSON:

```json
"last_error": {
  "category": "github.rate_limit",
  "transient": true,
  "original_type": "RateLimitError",
  "message": "Secondary rate limit encountered"
}
```

This mirrors the internal error taxonomy used for logging and allows downstream
automation or AI tooling to reason about retryability and categorize failures.

### Performance Benchmarking (Experimental)

IssueSuite includes an optional lightweight benchmarking layer that can capture
wall-clock timings (and optionally system metrics) for major sync phases
(`parse_specs`, `fetch_existing_issues`, `process_specs`, `save_hash_state`, `sync_total`).

Enable it in config (placeholder keys—subject to change):

```yaml
performance:
  enabled: true
```

Or via environment variable (future): `ISSUESUITE_BENCH=1`.

When enabled, a JSON report (default `performance_report.json`) is written
after a successful sync with structure similar to:

```json
{
  "operations": {
    "parse_specs": { "ms": 12.4 },
    "fetch_existing_issues": { "ms": 98.7 },
    "process_specs": { "ms": 210.3 },
    "save_hash_state": { "ms": 3.2 },
    "sync_total": { "ms": 332.1 }
  },
  "system": {
    "cpu_percent_avg": 14.2,
    "memory_rss_mb": 123.5
  }
}
```

Use this to identify unexpectedly slow phases (e.g. network-bound fetch) and
guide future concurrency tuning. Metrics are approximate and not intended for
fine-grained profiling—prefer `py-spy` or similar for deeper analysis.

Library helper:

```python
from issuesuite.schemas import get_schemas
schemas = get_schemas()
print(schemas.keys())  # dict_keys(['export','summary','ai_context'])

```

### Programmatic AI Context

Obtain the structured AI context document (same as `issuesuite ai-context` CLI output) directly:

```python
from issuesuite import get_ai_context, load_config
cfg = load_config('issue_suite.config.yaml')
ctx = get_ai_context(cfg, preview=3)
print(ctx['spec_count'], len(ctx['preview']))
```

Key fields:

- `schemaVersion`: versioned string (e.g. `ai-context/1`)
- `spec_count`: total parsed specs
- `preview`: truncated list (controlled by `preview` arg) of spec metadata (no bodies)
- `errors`: supported error categories + retry env values (`ISSUESUITE_RETRY_ATTEMPTS`, `ISSUESUITE_RETRY_BASE`) and strategy descriptor
- `mapping`: summary of internal mapping index (size, optional snapshot)
- `config`: selected behavioral flags (dry run default, truncation, concurrency)
- `env`: runtime environment flags (ai_mode, mock_mode, debug_logging)
- `project`: GitHub project configuration (presence, number, field mappings)
- `recommended`: safe command invocations, usage tips, and environment hints

Use this document when embedding IssueSuite into higher-level automation or AI workflows to avoid parsing raw Markdown on every step.

## Offline / Testing

```bash
ISSUES_SUITE_MOCK=1 issuesuite sync --dry-run --update --config issue_suite.config.yaml --summary-json summary.json
```

## AI Mode & Assistant Integration

### AI Mode (Forced Dry-Run)

Set `ISSUESUITE_AI_MODE=1` to guarantee side-effect free operation while experimenting with agents or exploratory tooling. The orchestrator augments the summary with `ai_mode: true` and silently upgrades any non-dry-run invocation to dry-run.

```bash
ISSUESUITE_AI_MODE=1 issuesuite sync --config issue_suite.config.yaml --update
# Internally treated as dry-run; no GitHub mutations occur.
```

This pairs well with mock mode for fully offline, zero-API evaluation:

```bash
ISSUESUITE_AI_MODE=1 ISSUES_SUITE_MOCK=1 issuesuite summary --config issue_suite.config.yaml
```

### AI Context Export (with Quiet Mode)

Produce a compact JSON snapshot designed for AI assistants:

```bash
# Basic
issuesuite ai-context --config issue_suite.config.yaml > ai_context.json

# Suppress incidental logging (clean JSON)
issuesuite ai-context --quiet --config issue_suite.config.yaml > ai_context.json
```

## Environment Variables

| Variable                           | Purpose                                                       | Default |
| ---------------------------------- | ------------------------------------------------------------- | ------- |
| `ISSUES_SUITE_MOCK`                | Enable mock/offline mode (no GitHub calls; deterministic IDs) | unset   |
| `ISSUESUITE_DEBUG`                 | Verbose debug logging                                         | unset   |
| `ISSUESUITE_AI_MODE`               | Force all sync operations into dry-run (safety)               | unset   |
| `ISSUESUITE_PROJECT_CACHE_TTL`     | Seconds before project field cache considered stale           | `3600`  |
| `ISSUESUITE_PROJECT_CACHE_DISABLE` | Disable on-disk project cache persistence when set to `1`     | unset   |
| `ISSUESUITE_QUIET`                 | Suppress non-error log lines for clean JSON piping            | unset   |
| `ISSUESUITE_RETRY_ATTEMPTS`        | Override retry attempts for transient GitHub CLI errors       | 3       |
| `ISSUESUITE_RETRY_BASE`            | Base seconds for exponential backoff                          | 0.5     |
| `ISSUESUITE_RETRY_MAX_SLEEP`       | Max seconds to sleep per retry (test/CI clamp)                | unset   |

## Reliability & Error Handling

IssueSuite layers several mechanisms to keep syncs stable and observable:

- Central retry abstraction (`issuesuite.retry.run_with_retries`) handles transient GitHub CLI failures (rate limit / abuse / secondary rate) with exponential backoff + jitter, honoring explicit `Retry-After` or `wait N seconds` hints when present. Tunable via `ISSUESUITE_RETRY_ATTEMPTS`, `ISSUESUITE_RETRY_BASE`, and optionally capped by `ISSUESUITE_RETRY_MAX_SLEEP` (useful in CI).
- Optional milestone governance (`milestone_required: true`) to enforce planning discipline (fails fast listing missing spec IDs).
- Structured error classification (scaffold) logs a `sync_failed` event with category & transient flag (categories: `github.rate_limit`, `github.abuse`, `network`, `parse`, `generic`).
- Redaction layer masks obvious secrets (GitHub tokens, embedded private keys) before structured logging.
- Quiet mode suppresses incidental info lines without hiding structured errors.

Planned extensions: richer error taxonomy (HTTP status extraction), partial token masking (prefix/suffix), and integration of error stats into AI context output.

Caching: project/field/option metadata is written to `.issuesuite_cache/project_<number>_cache.json` unless disabled. TTL controls refresh cadence when running multiple syncs (e.g., CI matrix jobs).

## Versioning & Release Alignment

Version: `__version__` in `issuesuite.__init__` must match `pyproject.toml`. See `CHANGELOG.md` for release notes.

Sample (abridged):

```jsonc
{
  "schemaVersion": "ai-context/1",
  "type": "issuesuite.ai-context",
  "spec_count": 12,
  "preview": [
    {
      "external_id": "100",
      "title": "Feature: Example",
      "hash": "abc123",
      "labels": ["meta:roadmap"],
      "milestone": "Sprint 0: Mobilize",
      "status": null,
    },
  ],
  "config": {
    "dry_run_default": false,
    "ensure_labels_enabled": false,
    "ensure_milestones_enabled": false,
    "truncate_body_diff": 80,
    "concurrency_enabled": false,
    "concurrency_max_workers": 4,
    "performance_benchmarking": false,
  },
  "env": {
    "ai_mode": false,
    "mock_mode": false,
    "debug_logging": false,
  },
  "recommended": {
    "safe_sync": "issuesuite sync --dry-run --update --config issue_suite.config.yaml",
    "export": "issuesuite export --config issue_suite.config.yaml --pretty",
    "summary": "issuesuite summary --config issue_suite.config.yaml",
    "usage": [
      "Use safe_sync for read-only diffing in AI mode",
      "Call export for full structured spec list when preview insufficient",
      "Prefer summary for quick human-readable validation before sync",
    ],
    "env": [
      "ISSUESUITE_AI_MODE=1 to force dry-run safety",
      "ISSUES_SUITE_MOCK=1 for offline parsing without GitHub API",
      "ISSUESUITE_QUIET=1 to suppress logs for clean JSON",
      "ISSUESUITE_DEBUG=1 for verbose debugging output",
    ],
  },
}
```

Guidance for tool builders:

- Detect and respect `ai_mode`; never attempt write operations unless the user explicitly disables it.
- Treat `spec_count` as an upper bound when planning chunked reasoning.
- Use `preview` to ground initial reasoning; fall back to export for full details.
- Fall back to `issuesuite export` for complete structured data when needed.
- Use `--quiet` (or `ISSUESUITE_QUIET=1`) when capturing JSON for downstream tooling to avoid parsing log lines.

## Breaking Change (vNext) — Slug + YAML Format

Legacy numeric headings like:

```markdown
## 001 | Old Style Title

## labels: bug

Body text
```

are no longer supported and will raise a `ValueError` (`Legacy numeric issue format detected`). Migrate by converting each entry to the slug + YAML block form. Migration steps:

1. Choose a stable slug (lowercase letters / digits / `-` / `_`).
2. Create heading: `## [slug: chosen-slug]`.
3. Move all metadata (title, labels, milestone, status, body, project fields) into a fenced YAML block.
4. Preserve body text under `body:` (use `|` or `>` for multi-line).
5. Remove the old divider (`---`).

The parser will auto-insert the hidden marker `<!-- issuesuite:slug=<slug> -->` into the body if absent, ensuring idempotent matching.

## Roadmap (Selected)

- GitHub Project (v2) assignment integration
- Concurrency for large roadmaps
- GitHub App token integration
- Performance benchmarking harness
- Two-way reconcile / import

## Versioning

Semantic versioning once extracted; `__version__` exported for tooling.

## Quality gates

Run the bundled helper to execute the release gate suite (tests, lint, type checks, security scan, secrets scan, build) with a minimum coverage threshold of 65%:

```bash
python scripts/quality_gates.py
```

The script prints a concise summary and writes `quality_gate_report.json` for CI dashboards.

The dependency gate first attempts to run `pip-audit` in the active environment and automatically falls back to IssueSuite's curated offline advisory dataset when network access is unavailable. The dataset lives at `src/issuesuite/data/security_advisories.json`; update it in tandem with upstream disclosures to keep offline scans trustworthy. You can also run the audit directly via `python -m issuesuite.dependency_audit` (pass `--offline-only` to skip the online probe).

For performance budgets, the gate suite now generates a deterministic `performance_report.json` before asserting benchmarks. You can refresh the artifact independently with:

```bash
python scripts/generate_performance_report.py --output performance_report.json
python -m issuesuite.benchmarking --check --report performance_report.json
```

The helper runs IssueSuite in mock mode against a synthetic roadmap, exercises sync and preflight flows, and produces metrics that are stable across environments—ideal for CI enforcement.

## License

MIT
