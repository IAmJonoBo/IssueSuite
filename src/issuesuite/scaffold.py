"""Project scaffolding helpers for IssueSuite."""

from __future__ import annotations

import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CONFIG_TEMPLATE = textwrap.dedent(
    """
    # IssueSuite configuration file
    # Docs: https://github.com/IAmJonoBo/IssueSuite
    version: 1
    source:
      file: {issues_filename}
      id_pattern: "^[a-z0-9][a-z0-9-_]*$"
    behavior:
      dry_run_default: true
      truncate_body_diff: 80
    defaults:
      ensure_labels_enabled: false
      ensure_milestones_enabled: false
    output:
      summary_json: issues_summary.json
      export_json: issues_export.json
      plan_json: issues_plan.json
      mapping_file: .issuesuite/index.json
      hash_state_file: .issuesuite/hashes.json
    ai:
      schema_version: 1
    """
).lstrip()

ISSUES_TEMPLATE = textwrap.dedent(
    """
    # IssueSuite backlog (edit or replace entries with your own)
    ## [slug: example-task]
    ```yaml
    title: Draft initial roadmap
    labels: [enhancement]
    milestone: Sprint 1
    status: open
    body: |
      Capture the headline deliverables and required context here.
    ```

    ## [slug: docs-refresh]
    ```yaml
    title: Refresh documentation
    labels: [documentation]
    status: open
    body: |
      Keep a running list of docs to update after adopting IssueSuite.
    ```
    """
).lstrip()

WORKFLOW_TEMPLATE = textwrap.dedent(
    """
    name: IssueSuite Sync

    on:
      workflow_dispatch:
      schedule:
        - cron: "0 12 * * 1"

    permissions:
      contents: read

    jobs:
      dry-run-sync:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v5

          - name: Set up Python
            uses: actions/setup-python@v6
            with:
              python-version: "3.12"

          - name: Install IssueSuite
            run: |
              python -m pip install --upgrade pip
              pip install issuesuite

          - name: Validate specs
            run: issuesuite validate --config issue_suite.config.yaml

          - name: Dry-run sync
            run: |
              issuesuite sync --dry-run --update --config issue_suite.config.yaml \
                --summary-json issues_summary.json --plan-json issues_plan.json

          - name: Upload plan artifacts
            uses: actions/upload-artifact@v4
            with:
              name: issuesuite-plan
              path: |
                issues_summary.json
                issues_plan.json
    """
).lstrip()

VSCODE_TASKS_TEMPLATE = textwrap.dedent(
    """
    {
      "version": "2.0.0",
      "tasks": [
        {
          "label": "IssueSuite: Validate",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "validate",
            "--config",
            "issue_suite.config.yaml"
          ],
          "group": "build"
        },
        {
          "label": "IssueSuite: Dry-run Sync",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "sync",
            "--dry-run",
            "--update",
            "--config",
            "issue_suite.config.yaml",
            "--summary-json",
            "issues_summary.json",
            "--plan-json",
            "issues_plan.json"
          ],
          "group": {
            "kind": "build",
            "isDefault": true
          }
        },
        {
          "label": "IssueSuite: Full Sync",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "sync",
            "--update",
            "--config",
            "issue_suite.config.yaml",
            "--summary-json",
            "issues_summary.json"
          ],
          "group": "build"
        }
      ]
    }
    """
).lstrip()

VSCODE_LAUNCH_TEMPLATE = textwrap.dedent(
    """
    {
      "version": "0.2.0",
      "configurations": [
        {
          "name": "IssueSuite: Dry-run Sync",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "sync",
            "--dry-run",
            "--update",
            "--config",
            "issue_suite.config.yaml"
          ],
          "justMyCode": false,
          "console": "integratedTerminal"
        },
        {
          "name": "IssueSuite: Validate",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "validate",
            "--config",
            "issue_suite.config.yaml"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        }
      ]
    }
    """
).lstrip()

VSCODE_SETTINGS_TEMPLATE = textwrap.dedent(
    """
    {
      "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
      "python.envFile": "${workspaceFolder}/.env",
      "python.testing.pytestEnabled": true,
      "python.testing.pytestArgs": [
        "tests"
      ],
      "yaml.schemas": {
        "./issue_suite.schema.json": [
          "issue_suite.config.yaml",
          "**/.issuesuite/**/*.yaml"
        ],
        "./ai_context.schema.json": [
          "**/.issuesuite/**/*.json"
        ]
      },
      "files.watcherExclude": {
        "**/.issuesuite/**": true
      },
      "search.exclude": {
        "**/.issuesuite/**": true,
        "issues_summary.json": true,
        "issues_plan.json": true,
        "issues_export.json": true
      }
    }
    """
).lstrip()

GITIGNORE_TEMPLATE = textwrap.dedent(
    """
    # IssueSuite artifacts
    issues_summary.json
    issues_export.json
    issues_plan.json
    .issuesuite/
    """
).lstrip()


@dataclass
class ScaffoldResult:
    created: list[Path]
    skipped: list[Path]


def _write_if_needed(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _iter_optional_templates(include: Iterable[str]) -> list[tuple[str, str, str]]:
    mapping = {
        "workflow": (
            ".github/workflows/issuesuite-sync.yml",
            WORKFLOW_TEMPLATE,
            "GitHub workflow",
        ),
        "gitignore": (".gitignore", GITIGNORE_TEMPLATE, ".gitignore entries"),
    }
    results: list[tuple[str, str, str]] = []
    for key in include:
        if key in mapping:
            results.append(mapping[key])
    return results


_VSCODE_ASSET_TEMPLATES: dict[str, tuple[str, str]] = {
    "tasks": (".vscode/tasks.json", VSCODE_TASKS_TEMPLATE),
    "launch": (".vscode/launch.json", VSCODE_LAUNCH_TEMPLATE),
    "settings": (".vscode/settings.json", VSCODE_SETTINGS_TEMPLATE),
}

_DEFAULT_VSCODE_ASSETS: tuple[str, ...] = ("tasks", "launch", "settings")


def write_vscode_assets(
    directory: Path,
    *,
    force: bool = False,
    assets: Iterable[str] | None = None,
) -> ScaffoldResult:
    """Ensure VS Code assets exist under *directory*."""

    selected = list(dict.fromkeys(assets or _DEFAULT_VSCODE_ASSETS))
    created: list[Path] = []
    skipped: list[Path] = []

    for asset in selected:
        template_info = _VSCODE_ASSET_TEMPLATES.get(asset)
        if not template_info:
            continue
        rel_path, template = template_info
        target = (directory / rel_path).resolve()
        if _write_if_needed(target, template, force):
            created.append(target)
        else:
            skipped.append(target)

    return ScaffoldResult(created=created, skipped=skipped)


def write_vscode_tasks(directory: Path, *, force: bool = False) -> ScaffoldResult:
    """Ensure VS Code task definitions exist under *directory*."""

    return write_vscode_assets(directory, force=force, assets=("tasks",))


def scaffold_project(
    directory: Path,
    *,
    issues_filename: str = "ISSUES.md",
    config_filename: str = "issue_suite.config.yaml",
    force: bool = False,
    include: Iterable[str] | None = None,
) -> ScaffoldResult:
    """Create IssueSuite starter files under *directory*.

    Parameters
    ----------
    directory:
        Target root directory. Created if missing.
    issues_filename / config_filename:
        Names of the primary specification files.
    force:
        Overwrite existing files when true.
    include:
        Optional iterable of extras ("workflow", "vscode", "gitignore").
        Selecting "vscode" writes tasks, launch, and settings files.
    """

    directory.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    skipped: list[Path] = []

    config_path = directory / config_filename
    issues_path = directory / issues_filename

    config_content = CONFIG_TEMPLATE.format(issues_filename=issues_filename)
    if _write_if_needed(config_path, config_content, force):
        created.append(config_path)
    else:
        skipped.append(config_path)

    if _write_if_needed(issues_path, ISSUES_TEMPLATE, force):
        created.append(issues_path)
    else:
        skipped.append(issues_path)

    extras = include or []
    if "vscode" in extras:
        vscode_result = write_vscode_assets(directory, force=force)
        created.extend(vscode_result.created)
        skipped.extend(vscode_result.skipped)
    filtered_extras = [item for item in extras if item != "vscode"]
    for rel_path, template, _label in _iter_optional_templates(filtered_extras):
        target = directory / rel_path
        if _write_if_needed(target, template, force):
            created.append(target)
        else:
            skipped.append(target)

    return ScaffoldResult(created=created, skipped=skipped)


__all__ = [
    "scaffold_project",
    "ScaffoldResult",
    "write_vscode_tasks",
    "write_vscode_assets",
]
