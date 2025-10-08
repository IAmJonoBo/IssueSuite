# Extensions, Plugins, and Telemetry

IssueSuite ships optional hooks so teams can observe CLI usage and run custom logic after each command.

## Plugin entry points

- Entry point group: `issuesuite.plugins`.
- Plugins receive a `PluginContext` containing the command name, the loaded `SuiteConfig`, and a payload dictionary (which may include summaries or upgrade suggestions).
- Disable plugins globally via `extensions.enabled: false` or skip specific hooks with `extensions.disabled` in `issue_suite.config.yaml`.
- Provide ad-hoc plugins through the environment variable `ISSUESUITE_PLUGINS="module:path_to_callable"`.

## Telemetry (opt-in)

- Controlled through the `telemetry` block in the config or `ISSUESUITE_TELEMETRY` environment variable.
- Events are appended to `${HOME}/.issuesuite/telemetry.jsonl` by default. Override with `telemetry.store_path` or `ISSUESUITE_TELEMETRY_PATH`.
- Each event captures timestamp, command, exit code, duration in milliseconds, and the IssueSuite version. No spec content is recorded.
- Telemetry is best used to monitor CLI adoption or spot long-running operations locally.

## Upgrade assistant

The `issuesuite upgrade` command reviews current configuration defaults and surfaces actionable recommendations in text or JSON form:

- Suggest moving legacy `.issuesuite_mapping.json` files to the consolidated `.issuesuite/index.json` format.
- Encourage enabling telemetry where helpful for local observability.
- Flag disabled extensions so teams can revisit intentional overrides.

Integrate the command into CI to keep configurations aligned with new defaults.
