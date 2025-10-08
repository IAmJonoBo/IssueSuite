# Getting Started with IssueSuite

This tutorial walks you from zero to a working IssueSuite project in under ten minutes. Along the way you'll scaffold starter files, run a preflight dry-run, and confirm your GitHub authentication.

## Prerequisites

- Python 3.11 or newer.
- A GitHub repository where IssueSuite will manage issues.
- (Optional) [`pipx`](https://pypa.github.io/pipx/) for isolated CLI installs.

## 1. Install the CLI

```bash
pipx install issuesuite
# or
pip install issuesuite
```

Verify the installation:

```bash
issuesuite --help
```

## 2. Scaffold a project workspace

Run the scaffolder inside your repository to generate configuration, specifications, automation scripts, and editor tasks:

```bash
issuesuite init --all-extras
```

The command creates:

| File | Purpose |
| --- | --- |
| `issue_suite.config.yaml` | Primary configuration referencing `ISSUES.md` |
| `ISSUES.md` | Sample backlog containing two editable issues |
| `.github/workflows/issuesuite-sync.yml` | Scheduled dry-run workflow template |
| `.vscode/tasks.json` | One-click Validate, Dry-run Sync, and Full Sync tasks |
| `scripts/issuesuite-preflight.sh` | Convenience script to run local validations |

Re-run with `--force` to overwrite or use `--include` to request specific extras.

## 3. Run a local preflight

Execute the bundled script to validate the spec and produce machine-readable summaries:

```bash
./scripts/issuesuite-preflight.sh
```

Artifacts include:

- `issues_summary.json`: Aggregated plan totals.
- `issues_plan.json`: Dry-run action plan for CI review.

Prefer VS Code? Launch the **IssueSuite: Preflight** task, which runs the same checks.

## 4. Wire authentication

Export a GitHub token (classic token with `repo` scope or a GitHub App installation) into your environment or `.env` file, then run:

```bash
issuesuite setup --check-auth
```

The doctor reports whether tokens are detected, if GitHub App credentials are present, and whether the workspace is in mock mode.

## 5. Promote to a full sync

Once your dry-run looks good, enable mutations:

```bash
issuesuite sync \
  --update \
  --config issue_suite.config.yaml \
  --summary-json issues_summary.json
```

Tips:

- Add `--preflight` the first time you run against a repository to auto-create labels and milestones.
- Set `behavior.dry_run_default: true` in the config if you want all CLI runs to stay read-only until you explicitly add `--update`.

## 6. Explore next steps

- Use `issuesuite summary` to print a quick backlog overview.
- Run `issuesuite export --pretty` to generate JSON for integrations.
- Generate AI context with `issuesuite ai-context --preview 10` for assistants.
- Continue to the [How-to guides](../how-to/README.md) for CI/CD, editor integration, and advanced workflows.
