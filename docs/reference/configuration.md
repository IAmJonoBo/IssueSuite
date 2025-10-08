# Configuration Reference

IssueSuite reads settings from `issue_suite.config.yaml`. The schema is divided into sections; defaults are shown where helpful.

## `version`

Current configuration version. Leave at `1` unless instructed otherwise.

## `source`

| Key                  | Type   | Default                 | Description                                  |
| -------------------- | ------ | ----------------------- | -------------------------------------------- |
| `file`               | string | `ISSUES.md`             | Path to the spec file relative to the config |
| `id_pattern`         | regex  | `^[a-z0-9][a-z0-9-_]*$` | Allowed slug format                          |
| `milestone_required` | bool   | `false`                 | Require each spec to provide a milestone     |
| `milestone_pattern`  | regex  | —                       | Enforce milestone naming conventions         |

## `defaults`

| Key                         | Type      | Default                     | Description                              |
| --------------------------- | --------- | --------------------------- | ---------------------------------------- |
| `inject_labels`             | list[str] | `[]`                        | Labels added to every issue when syncing |
| `ensure_labels_enabled`     | bool      | `false`                     | Create missing labels automatically      |
| `ensure_milestones_enabled` | bool      | `false`                     | Create missing milestones automatically  |
| `ensure_milestones`         | list[str] | Predefined milestone ladder | Ensures required milestones exist        |

## `behavior`

| Key                  | Type | Default | Description                                      |
| -------------------- | ---- | ------- | ------------------------------------------------ |
| `dry_run_default`    | bool | `false` | Force dry-run mode unless `--update` is provided |
| `truncate_body_diff` | int  | `80`    | Length of diff previews in plan output           |
| `emit_change_events` | bool | `false` | Enable change event emission for integrations    |

## `output`

| Key               | Default                    | Purpose                                                      |
| ----------------- | -------------------------- | ------------------------------------------------------------ |
| `summary_json`    | `issues_summary.json`      | Sync totals and plan summary                                 |
| `plan_json`       | `issues_plan.json`         | Dry-run action plan (`sync --plan-json`)                     |
| `export_json`     | `issues_export.json`       | Output for `issuesuite export`                               |
| `report_html`     | `issues_report.html`       | Reserved for future HTML reports                             |
| `hash_state_file` | `.issuesuite_hashes.json`  | Tracks spec hashes to detect changes                         |
| `mapping_file`    | `.issuesuite_mapping.json` | Legacy mapping file (superseded by `.issuesuite/index.json`) |
| `lock_file`       | `.issuesuite_lock`         | Prevents concurrent runs                                     |

## `github`

| Key                      | Default | Description                                                                          |
| ------------------------ | ------- | ------------------------------------------------------------------------------------ |
| `repo`                   | `null`  | `owner/repo` identifier for the target repository                                    |
| `project.enable`         | `false` | Opt into GitHub Projects (v2) integration                                            |
| `project.number`         | `null`  | Project number when enabled                                                          |
| `project.field_mappings` | `{}`    | Map IssueSuite metadata to project fields                                            |
| `app.enabled`            | `false` | Use GitHub App authentication                                                        |
| `app.*`                  | —       | `app_id`, `private_key_path`, `installation_id`; can reference environment variables |

## `logging`

| Key            | Default | Description               |
| -------------- | ------- | ------------------------- |
| `json_enabled` | `false` | Emit structured JSON logs |
| `level`        | `INFO`  | Minimum log level         |

## `performance`

| Key            | Default | Description                                           |
| -------------- | ------- | ----------------------------------------------------- |
| `benchmarking` | `false` | Emit performance metrics to `performance_report.json` |

## `concurrency`

| Key           | Default | Description                               |
| ------------- | ------- | ----------------------------------------- |
| `enabled`     | `false` | Enable parallel GitHub operations         |
| `max_workers` | `4`     | Number of concurrent workers when enabled |

## `environment`

| Key           | Default | Description                           |
| ------------- | ------- | ------------------------------------- |
| `enabled`     | `true`  | Enable environment helper integration |
| `load_dotenv` | `true`  | Load `.env` automatically             |
| `dotenv_path` | `null`  | Custom `.env` path                    |

## `telemetry`

| Key          | Default                             | Description                             |
| ------------ | ----------------------------------- | --------------------------------------- |
| `enabled`    | `false`                             | Opt into local telemetry (JSONL events) |
| `store_path` | `$HOME/.issuesuite/telemetry.jsonl` | Destination for captured events         |

## `extensions`

| Key        | Default | Description                          |
| ---------- | ------- | ------------------------------------ |
| `enabled`  | `true`  | Enable plugin loading                |
| `disabled` | `[]`    | Names of entry-point plugins to skip |

## Tips

- Use environment variables in YAML values via the `$VARNAME` syntax; IssueSuite resolves them at load time.
- Combine `defaults.ensure_labels_enabled` with `sync --preflight` to bootstrap labels on first run.
- For air-gapped environments, set `ISSUES_SUITE_MOCK=1` to bypass GitHub API calls while exercising the pipeline.

Consult the [CLI reference](cli.md) for command-level options and the [Architecture notes](../explanations/architecture.md) for module-level details.
