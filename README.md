# IssueSuite

Declarative GitHub Issues automation — manage a roadmap from a single `ISSUES.md` file and keep real GitHub issues perfectly in sync (create / update / close) with deterministic hashes, readable diffs, JSON artifacts, and optional preflight resource creation.

## Features

- Single source of truth in Markdown (`ISSUES.md`)
- Idempotent create/update/close using stable external IDs & content hashes
- Human & machine-readable diffs (labels, milestone, body snippet)
- JSON export (`issues_export.json`) + change summary (`issues_summary.json`)
- HTML roadmap report generation (legacy script; optional in future extraction)
- Configurable patterns (ID regex, milestone naming, global injected labels)
- Optional preflight auto-create of labels & milestones (feature flags)
- AI tooling: generated JSON Schemas for export & change summary (+ `issuesuite.schemas.get_schemas()`)
- AI mode (safety): `ISSUESUITE_AI_MODE=1` forces all syncs into dry-run (no mutations) even if `--dry-run` omitted
- AI context export: `issuesuite ai-context` emits structured JSON (preview of spec, config hints, env suggestions) for assistant ingestion
- Quiet mode: `--quiet` or `ISSUESUITE_QUIET=1` suppresses informational logging (helpful when piping JSON to other tools)
- Debug logging via `ISSUESUITE_DEBUG=1`
- Mock mode (`ISSUES_SUITE_MOCK=1`) for offline tests w/out GitHub API
  - In mock mode all GitHub CLI calls are suppressed (even without `--dry-run`) and operations are printed as `MOCK <action>`.

## Quick Start

```bash
# Install from PyPI
pip install issuesuite

# Or install with pipx (recommended for CLI usage)
pipx install issuesuite

# Or install directly from GitHub
pip install git+https://github.com/IAmJonoBo/IssueSuite.git

# Validate structure & ID pattern
issuesuite validate --config issue_suite.config.yaml

# Dry-run sync (no mutations) with summary JSON output
issuesuite sync --dry-run --update --config issue_suite.config.yaml --summary-json issues_summary.json

# Export current parsed specs
issuesuite export --pretty --config issue_suite.config.yaml --output issues_export.json

# Human-readable summary
issuesuite summary --config issue_suite.config.yaml

# Emit schemas to stdout (or files when omitting --stdout)
issuesuite schema --stdout
```

## Configuration (`issue_suite.config.yaml`)

Key sections:

```yaml
version: 1
source:
  file: ISSUES.md
  id_pattern: "^[0-9]{3}$"
  milestone_required: true
  milestone_pattern: "^(Sprint 0:|M[0-9]+:)"
defaults:
  inject_labels: [meta:roadmap, managed:declarative]
  ensure_milestones: ["Sprint 0: Mobilize & Baseline"]
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
behavior:
  truncate_body_diff: 80
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

## JSON Schemas

Generate schemas (export + change summary):
CLI:

```bash
issuesuite schema --config issue_suite.config.yaml
```

Library helper:

```python
from issuesuite.schemas import get_schemas
schemas = get_schemas()
```

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

## Roadmap

- Structured JSON logging option
- GitHub Project (v2) assignment integration
- Concurrency for large roadmaps
- GitHub App token integration
- Performance benchmarking harness

## Versioning

Semantic versioning once extracted; `__version__` exported for tooling.

## License

MIT
