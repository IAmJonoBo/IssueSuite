# Use IssueSuite inside VS Code

The scaffolder ships a `.vscode/tasks.json` file so common workflows are one click away.

## Provided tasks

| Task                                  | Description                                                                                        |
| ------------------------------------- | -------------------------------------------------------------------------------------------------- |
| IssueSuite: Preflight                 | Runs `scripts/issuesuite-preflight.sh` to validate specs and perform a dry-run sync                |
| IssueSuite: DX Sweep                  | Executes `scripts/issuesuite-dx-sweep.sh` producing summaries, exports, schemas, and AI context    |
| IssueSuite: DX Sweep (with reconcile) | Adds a reconcile check to the DX sweep and tolerates intentional drift                             |
| Legacy tasks                          | `Validate`, `Dry-run Sync`, `Full Sync`, and `Agent Apply` remain available for advanced scenarios |

Launch them via **Terminal → Run Task…** or the Command Palette.

## Recommended extensions

- **YAML (Red Hat)** for schema-aware editing of `issue_suite.config.yaml`.
- **GitHub Pull Requests & Issues** to cross-reference specs with live issues.
- **EditorConfig** to stay consistent with generated files.

## Debugging tips

- Toggle `ISSUESUITE_DEBUG=1` in a task definition to inspect GitHub payloads.
- Enable `ISSUESUITE_QUIET=1` when consuming JSON output programmatically.
- Re-run `issuesuite setup --vscode` after manual scaffolding to regenerate integration files.
