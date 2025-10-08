# CLI Reference

The `issuesuite` command exposes subcommands for validation, synchronization, and tooling. This reference summarizes the most common options. Run `issuesuite <command> --help` for the complete argument list.

## Common global flags

| Flag      | Description                                                      |
| --------- | ---------------------------------------------------------------- |
| `--quiet` | Suppress informational logs (equivalent to `ISSUESUITE_QUIET=1`) |

Most commands default to reading `issue_suite.config.yaml`. Override with `--config <path>`.

## Subcommands

| Command                  | Purpose                                                      | Key Options                                                                                            |
| ------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `issuesuite init`        | Scaffold config, specs, workflows, and editor tasks          | `--all-extras`, `--include`, `--force`                                                                 |
| `issuesuite validate`    | Parse specs and enforce slug patterns                        | —                                                                                                      |
| `issuesuite summary`     | Print a quick backlog overview                               | `--limit`, `--repo`                                                                                    |
| `issuesuite sync`        | Create/update/close issues against GitHub                    | `--dry-run`, `--update`, `--summary-json`, `--plan-json`, `--preflight`, `--prune`, `--respect-status` |
| `issuesuite export`      | Emit parsed issues as JSON                                   | `--output`, `--pretty`, `--repo`                                                                       |
| `issuesuite import`      | Draft `ISSUES.md` from live issues                           | `--output`, `--limit`, `--repo`                                                                        |
| `issuesuite reconcile`   | Compare local specs with live issues without mutating        | `--limit`, `--repo`                                                                                    |
| `issuesuite schema`      | Generate JSON Schemas for exports and summaries              | `--stdout`                                                                                             |
| `issuesuite ai-context`  | Produce machine-readable context for AI tooling              | `--preview`, `--output`, `--quiet`                                                                     |
| `issuesuite agent-apply` | Apply AI agent suggestions and optionally sync               | `--updates-json`, `--apply`, `--no-sync`, `--respect-status`, `--dry-run-sync`, `--summary-json`       |
| `issuesuite doctor`      | Diagnose authentication, repo access, and environment flags  | `--repo`                                                                                               |
| `issuesuite setup`       | Generate VS Code assets or check auth state                  | `--create-env`, `--check-auth`, `--vscode`                                                             |
| `issuesuite upgrade`     | Recommend config migrations (mapping, telemetry, extensions) | `--json`                                                                                               |

## Exit codes

| Code | Meaning                                                                                |
| ---- | -------------------------------------------------------------------------------------- |
| `0`  | Command succeeded                                                                      |
| `1`  | Command failed (validation error, exception, or recommendations produced by `upgrade`) |
| `2`  | Drift detected (used by `reconcile` and some doctor checks)                            |

## Environment variables

| Variable                 | Effect                                        |
| ------------------------ | --------------------------------------------- |
| `ISSUESUITE_QUIET=1`     | Suppress info logs (equivalent to `--quiet`)  |
| `ISSUESUITE_AI_MODE=1`   | Force dry-run mode (no mutations)             |
| `ISSUES_SUITE_MOCK=1`    | Use mock integrations for offline development |
| `ISSUESUITE_TELEMETRY=1` | Force telemetry on (`0` to force off)         |
| `ISSUESUITE_DRY_FORCE=1` | Impose dry-run mode regardless of CLI flags   |

See [Configuration reference](configuration.md) for details on YAML fields that back these behaviors.
