# IssueSuite

[![PyPI Version](https://img.shields.io/pypi/v/issuesuite.svg)](https://pypi.org/project/issuesuite/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/IAmJonoBo/IssueSuite)
[![Python Versions](https://img.shields.io/pypi/pyversions/issuesuite.svg)](https://pypi.org/project/issuesuite/)
[![CI](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/ci.yml/badge.svg)](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/ci.yml)
[![Lint](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/lint.yml/badge.svg)](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/lint.yml)
[![Test Build](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/test-build.yml/badge.svg)](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/test-build.yml)
[![UX Acceptance](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/ux-acceptance.yml/badge.svg)](https://github.com/IAmJonoBo/IssueSuite/actions/workflows/ux-acceptance.yml)

Declarative GitHub Issues automation — manage a roadmap from a single `ISSUES.md` file (using **slug headings + fenced YAML blocks**) and keep real GitHub issues perfectly in sync (create / update / close) with deterministic hashes, readable diffs, JSON artifacts, and optional preflight resource creation.

## Features

### Core Capabilities

- **Single source of truth**: Manage all issues from a single `ISSUES.md` file using slug-based headings and YAML blocks
- **Idempotent sync**: Stable mappings ensure updates never create duplicates
- **Dry-run mode**: Preview all changes before applying them to GitHub
- **Human-readable diffs**: See exactly what will change (labels, milestones, body snippets)
- **GitHub Projects (v2) integration**: Automatically sync issues to project boards with custom field mappings
- **Offline-ready**: Works in air-gapped environments with mock mode

### Issue Format

Each issue uses a simple, readable format:

```markdown
## [slug: api-timeouts]

\`\`\`yaml
title: Investigate API timeouts
labels: [bug, backend]
milestone: Sprint 1
body: |
  Requests intermittently exceed 5s …
\`\`\`
```

The parser requires: a level-2 heading with `[slug: <slug>]` followed by a fenced YAML block.

### Advanced Features

- **JSON artifacts**: Export specs (`issues_export.json`) and change summaries (`issues_summary.json`) with versioned schemas
- **AI/Agent integration**: Generate AI context and apply agent updates programmatically
- **Extensible**: Plugin system with telemetry hooks for custom workflows
- **Quality gates**: Built-in dependency scanning, security advisories, and compliance checks
- **Mock mode**: Full offline testing without GitHub API calls (`ISSUES_SUITE_MOCK=1`)
- **CI/CD ready**: Drift detection, automated preflight, and controlled apply pipelines

## Quick Start

### Installation

Install IssueSuite using `pipx` (recommended) or `pip`:

```bash
pipx install issuesuite
# or
pip install issuesuite
```

Verify the installation:

```bash
issuesuite --help
```

### Initialize Your Workspace

Generate a ready-to-run workspace with configuration, documentation, and CI workflows:

```bash
issuesuite init --all-extras
```

This creates:
- `issue_suite.config.yaml` — Configuration file
- `ISSUES.md` — Starter issue specifications
- `.vscode/tasks.json` — VS Code tasks for common operations
- `.github/workflows/` — CI workflow templates
- `.gitignore` updates — Artifact exclusions

### Your First Sync

1. **Edit your issue specs** in `ISSUES.md`:

   ```markdown
   ## [slug: welcome-issue]
   
   \`\`\`yaml
   title: Welcome to IssueSuite!
   labels: [documentation]
   milestone: Getting Started
   body: |
     This is your first managed issue.
   \`\`\`
   ```

2. **Run a dry-run** to preview changes:

   ```bash
   issuesuite sync --dry-run --config issue_suite.config.yaml
   ```

3. **Review the plan** in `issues_plan.json` and terminal output

4. **Apply the sync** when ready:

   ```bash
   issuesuite sync --update --config issue_suite.config.yaml
   ```

   **Tip**: Add `--preflight` to auto-create labels and milestones on first sync.

### Common Commands

```bash
# Validate issue specifications
issuesuite validate --config issue_suite.config.yaml

# Export issues as JSON
issuesuite export --pretty --config issue_suite.config.yaml

# Generate a backlog summary
issuesuite summary --config issue_suite.config.yaml

# Check authentication
issuesuite setup --check-auth

# Generate JSON Schemas
issuesuite schema --config issue_suite.config.yaml
```

### Next Steps

- 📖 **[Getting Started Tutorial](docs/starlight/src/content/docs/tutorials/getting-started.mdx)** — Detailed walkthrough with troubleshooting
- ⚙️ **[Configuration Reference](docs/starlight/src/content/docs/reference/configuration.mdx)** — All configuration options
- 🔧 **[CI/CD Automation](docs/starlight/src/content/docs/how-to/automation-ci.mdx)** — Wire IssueSuite into GitHub Actions
- 📋 **[GitHub Projects Integration](docs/starlight/src/content/docs/how-to/github-projects.mdx)** — Sync issues to project boards
- 🏗️ **[Architecture Overview](docs/starlight/src/content/docs/explanations/architecture.mdx)** — Understand how IssueSuite works

## Documentation

IssueSuite documentation uses the [Diátaxis framework](https://diataxis.fr/) and is built with [Astro Starlight](https://starlight.astro.build/):

- **Tutorials**: Learning-oriented guides for newcomers → [Getting started](docs/starlight/src/content/docs/tutorials/getting-started.mdx)
- **How-to guides**: Task-oriented instructions → [CI/CD automation](docs/starlight/src/content/docs/how-to/automation-ci.mdx), [GitHub Projects](docs/starlight/src/content/docs/how-to/github-projects.mdx), [Renovate integration](docs/starlight/src/content/docs/how-to/renovate-integration.mdx)
- **Reference**: Authoritative technical specs → [CLI commands](docs/starlight/src/content/docs/reference/cli.mdx), [Configuration](docs/starlight/src/content/docs/reference/configuration.mdx), [Environment variables](docs/starlight/src/content/docs/reference/environment-variables.mdx)
- **Explanations**: Design decisions and context → [Architecture](docs/starlight/src/content/docs/explanations/architecture.mdx), [Index mapping](docs/starlight/src/content/docs/explanations/index-mapping-design.mdx)

**Online documentation**: Visit [https://iamjonobo.github.io/IssueSuite/](https://iamjonobo.github.io/IssueSuite/) for the latest published version.

**Build documentation locally**:

```bash
cd docs/starlight
npm install
npm run dev  # Live preview at http://localhost:4321
```

Or use the nox session:

```bash
nox -s docs
```

## Contributing

IssueSuite welcomes contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development workflow and environment setup
- Quality gates and testing requirements
- Code style and formatting guidelines
- Documentation updates and ADR governance

### Quick Developer Setup

1. **Clone and install with development dependencies**:

   ```bash
   git clone https://github.com/IAmJonoBo/IssueSuite.git
   cd IssueSuite
   pip install -e .[dev,all]
   ```

2. **Configure development environment**:

   ```bash
   ./scripts/setup-dev-env.sh  # Installs hooks, validates setup
   issuesuite doctor  # Verify environment health
   ```

3. **Run quality gates locally**:

   ```bash
   nox -s tests lint typecheck security
   ```

### Developer Tooling

IssueSuite provides nox sessions for common development tasks:

```bash
nox -s tests          # Run test suite with coverage
nox -s lint           # Run ruff linter
nox -s typecheck      # Run mypy type checker
nox -s security       # Run security scanners
nox -s docs           # Build and check documentation
nox -s lock           # Refresh lockfiles (uv.lock, package-lock.json)
```

**Pre-commit hooks** automatically run format checks and lockfile validation:

```bash
git config core.hooksPath .githooks  # Enable local hooks
```

### Tool Versions

Development tools should match CI (handled by `pip install -e .[dev]`):

- Python: 3.10+ (CI tests 3.10, 3.11, 3.12, 3.13)
- ruff: 0.14 (pinned)
- mypy: 1.8+
- Node.js: 20+ (for docs)

See [ADR-0004](docs/adrs/ADR-0004-dev-environment-parity.md) for environment parity rationale.

## Authentication

IssueSuite supports multiple authentication methods:

### GitHub Personal Access Token (Classic)

1. Create a token with `repo` scope at https://github.com/settings/tokens
2. Export as environment variable:
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   ```

### GitHub App

For organization-wide deployments:

```yaml
github:
  app:
    enabled: true
    app_id: $GITHUB_APP_ID
    installation_id: $GITHUB_APP_INSTALLATION_ID
    private_key_path: $GITHUB_APP_PRIVATE_KEY_PATH
```

See [Environment Variables Reference](docs/starlight/src/content/docs/reference/environment-variables.mdx) for GitHub App configuration.

### Verify Authentication

Check authentication before syncing:

```bash
issuesuite setup --check-auth
```

Generate a starter `.env` file:

```bash
issuesuite setup --create-env
```

## Offline/Hermetic Deployment

IssueSuite supports air-gapped and hermetic environments for secure deployments:

**Core offline capabilities**:
- Works without network access when `ISSUES_SUITE_MOCK=1` is set
- Optional dependencies gracefully degrade if unavailable
- Offline testing validated in CI

**Offline installation**:

```bash
# 1. Build wheel
python -m build

# 2. Download dependencies
mkdir -p offline-wheels
pip download --dest offline-wheels dist/*.whl

# 3. Transfer to target environment and install
pip install --no-index --find-links ./offline-wheels issuesuite

# 4. Use mock mode for validation
export ISSUES_SUITE_MOCK=1
export ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE=1
issuesuite validate --config issue_suite.config.yaml
```

**Environment variables for offline operation**:

- `ISSUES_SUITE_MOCK=1` — Mock GitHub API calls (no network)
- `ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE=1` — Disable pip-audit network requests
- `ISSUESUITE_PROJECT_CACHE_DISABLE=1` — Disable GitHub Projects cache

See [CONTRIBUTING.md](CONTRIBUTING.md) for full offline development workflow and [Environment Variables Reference](docs/starlight/src/content/docs/reference/environment-variables.mdx) for all options.

## Advanced Features

### Agent Integration

Use `agent-apply` to let AI agents update `ISSUES.md` and trigger syncs:

```bash
# Dry-run: apply updates and preview sync
issuesuite agent-apply --updates-json updates.json

# Apply updates and sync to GitHub
issuesuite agent-apply --updates-json updates.json --apply

# Only update files, skip sync
issuesuite agent-apply --updates-json updates.json --no-sync
```

See [agent_updates.json](agent_updates.json) for JSON schema examples.

### Telemetry and Plugins

Enable observability with structured event logging:

```yaml
telemetry:
  enabled: true
  store_path: .issuesuite/telemetry.jsonl

extensions:
  enabled: true
  disabled: []
```

Tail `telemetry.jsonl` to monitor command usage. Custom plugins can hook into the same event stream.

See [Extensions and Telemetry](docs/starlight/src/content/docs/explanations/extensions.mdx) for details.

### Guided Setup

Run an interactive setup wizard:

```bash
issuesuite setup --guided
```

This inspects your workspace and recommends next steps for automation-ready configuration.

---

For additional configuration options, library usage, and advanced topics, see the sections below.

### Developer Environment Setup

For contributors working on IssueSuite itself, follow these steps to ensure your local environment matches CI:

1. **Clone and install with all development dependencies**:

   ```bash
   git clone https://github.com/IAmJonoBo/IssueSuite.git
   cd IssueSuite
   pip install -e .[dev,all]
   ```

2. **Configure development environment** (recommended):

   ```bash
   ./scripts/setup-dev-env.sh
   ```

   This automated setup script:
   - Installs Git pre-commit hooks for format/lockfile checks
   - Validates lockfile synchronization
   - Checks tool version parity with CI
   - Provides environment diagnostics

3. **Verify your setup**:
   ```bash
   issuesuite doctor  # Check environment health
   nox -s tests lint typecheck  # Run quality gates locally
   ```

**Before committing changes**:

- Pre-commit hooks automatically run format checks and lockfile validation
- Update lockfiles after dependency changes: `./scripts/refresh-deps.sh`
- Run full quality gates: `nox -s tests lint typecheck security`

**Tool versions** should match CI (automatically handled by `pip install -e .[dev]`):

- Python: 3.10+ (CI tests 3.10, 3.11, 3.12, 3.13)
- ruff: 0.14 (pinned exact version)
- mypy: 1.8+
- Node.js: 20+ (for documentation builds)

See [ADR-0004](docs/adrs/ADR-0004-dev-environment-parity.md) for the architectural decision behind environment parity enforcement.

### Developer Tooling

Run the consolidated quality gates locally with the bundled `nox` sessions:

```bash
nox -s tests lint typecheck security secrets build
nox -s lock  # refresh uv.lock and docs/starlight/package-lock.json
```

Frontier Apex prototypes introduce two new harnesses you can run ad-hoc while we- Preview nightly GitHub Projects automation dry-runs with `issuesuite projects-sync --comment-output preview.md` (set the relevant environment variables or pass `--project-owner/--project-number` to target your dashboard).

Frontier Apex prototypes introduce two new harnesses you can run ad-hoc while we
stabilise the elevated standards:

```bash
# Emit strict mypy telemetry without failing the workflow
python scripts/type_coverage_report.py

# Validate CLI help ergonomics across critical subcommands
python scripts/ux_acceptance.py

# Export coverage history for GitHub Projects dashboards
python scripts/coverage_trends.py

# Generate a GitHub Projects status payload and Markdown summary
python scripts/projects_status_report.py

# Generate the same status artifacts directly from the CLI
issuesuite projects-status --output projects_status_report.json --comment-output projects_status.md
```

Enable the repo-managed pre-commit hook so commits automatically use the local
virtualenv without manual activation:

```bash
git config core.hooksPath .githooks
```

This looks for `.venv` (or `venv` / `.env`) under the repository root before
falling back to a globally installed `pre-commit`.

When dependency manifests change (for example, after Renovate bumps a package),
run `scripts/refresh-deps.sh` (or `nox -s lock`) to regenerate `uv.lock` and the
Starlight `package-lock.json`. Use `./scripts/refresh-deps.sh --check` in CI or
pre-merge validation to ensure lockfiles remain current.

When preparing release notes, use `scripts/update_changelog.py` to append a new entry without risking editor hangs caused by blocking file locks:

```bash
python scripts/update_changelog.py 0.1.12 \
  --highlight "Document schema registry and changelog guard" \
  --highlight "Ship developer nox sessions"
```

### Documentation

IssueSuite documentation now lives in an [Astro Starlight workspace](docs/starlight). Run `npm install && npm run build` (or `nox -s docs`) to validate content locally and publish via your preferred static hosting.

- Tutorials: [Getting started](docs/starlight/src/content/docs/tutorials/getting-started.mdx)
- How-to guides: [CI/CD automation](docs/starlight/src/content/docs/how-to/automation-ci.mdx), [Homebrew tap automation](docs/starlight/src/content/docs/how-to/homebrew.mdx), [Documentation pipeline](docs/starlight/src/content/docs/how-to/docs-automation.mdx)
- Reference: [CLI commands](docs/starlight/src/content/docs/reference/cli.mdx), [Configuration schema](docs/starlight/src/content/docs/reference/configuration.mdx)
- Explanations: [Architecture overview](docs/starlight/src/content/docs/explanations/architecture.mdx), [Documentation strategy](docs/starlight/src/content/docs/explanations/documentation-strategy.mdx)
- Architecture decisions: [ADR-0001 – Adopt Astro Starlight](docs/adrs/ADR-0001-starlight-migration.md)

### Learn more

Observability quick start: run `issuesuite upgrade --json` to see recommended configuration defaults and add a `telemetry` block, e.g.

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

## Roadmap

### v1.x (Completed) ✅
- GitHub Project (v2) assignment integration
- Concurrency for large roadmaps
- GitHub App token integration
- Performance benchmarking harness
- Two-way reconcile / import

### v2.0 Vision 🚀
IssueSuite 2.0 transforms the production-ready CLI into a comprehensive **AI-powered, multi-repository automation platform** with:
- 🌐 Multi-repo workspace orchestration (manage 100+ repos)
- 🤖 AI-assisted spec generation and smart suggestions
- 🖥️ Server mode with webhooks and REST API
- 🔌 Plugin marketplace and rich ecosystem
- 🏢 Enterprise features (SAML/SSO, audit logs, SOC 2)

**📚 Read More:**
- [Comprehensive Gap Analysis & 2.0 Roadmap](docs/GAP_ANALYSIS_2.0_ROADMAP.md) — 39-page deep dive
- [Executive Summary](docs/EXECUTIVE_SUMMARY_2.0.md) — Stakeholder-focused overview
- [Quick Reference](docs/QUICK_REFERENCE_2.0.md) — One-page summary

**Timeline:** 15 months (Q1 2026 - Q1 2027) | **Status:** Strategic planning, RFC coming soon

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
