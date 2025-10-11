"""Project scaffolding helpers for IssueSuite."""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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
        },
        {
          "label": "IssueSuite: Summary",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "summary",
            "--config",
            "issue_suite.config.yaml",
            "--limit",
            "20"
          ],
          "group": "build"
        },
        {
          "label": "IssueSuite: Export",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "export",
            "--config",
            "issue_suite.config.yaml",
            "--pretty",
            "--output",
            "issues_export.json"
          ],
          "group": "build"
        },
        {
          "label": "IssueSuite: Agent Apply (dry-run)",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--updates-json",
            "agent_updates.json"
          ]
        },
        {
          "label": "IssueSuite: Agent Apply (apply)",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--updates-json",
            "agent_updates.json",
            "--apply"
          ]
        },
        {
          "label": "IssueSuite: Schema Bundle",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "schema",
            "--config",
            "issue_suite.config.yaml"
          ]
        },
        {
          "label": "IssueSuite: Projects Status",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "projects-status",
            "--config",
            "issue_suite.config.yaml"
          ]
        },
        {
          "label": "IssueSuite: Security Audit (Offline)",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "security",
            "--config",
            "issue_suite.config.yaml",
            "--offline-only",
            "--pip-audit",
            "--pip-audit-disable-online"
          ]
        },
        {
          "label": "IssueSuite: Guided Setup",
          "type": "shell",
          "command": "issuesuite",
          "args": [
            "setup",
            "--guided"
          ]
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
          "console": "integratedTerminal",
          "preLaunchTask": "IssueSuite: Validate"
        },
        {
          "name": "IssueSuite: Full Sync",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "sync",
            "--update",
            "--config",
            "issue_suite.config.yaml",
            "--summary-json",
            "issues_summary.json"
          ],
          "console": "integratedTerminal",
          "justMyCode": false,
          "preLaunchTask": "IssueSuite: Validate"
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
        },
        {
          "name": "IssueSuite: Summary",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "summary",
            "--config",
            "issue_suite.config.yaml",
            "--limit",
            "20"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        },
        {
          "name": "IssueSuite: Projects Status",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "projects-status",
            "--config",
            "issue_suite.config.yaml"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        },
        {
          "name": "IssueSuite: Security Audit (Offline)",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "security",
            "--config",
            "issue_suite.config.yaml",
            "--offline-only",
            "--pip-audit",
            "--pip-audit-disable-online"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        },
        {
          "name": "IssueSuite: Schema Bundle",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "schema",
            "--config",
            "issue_suite.config.yaml"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        },
        {
          "name": "IssueSuite: Guided Setup",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "setup",
            "--guided"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        },
        {
          "name": "IssueSuite: Agent Apply (dry-run)",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--updates-json",
            "agent_updates.json"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        },
        {
          "name": "IssueSuite: Agent Apply (apply)",
          "type": "python",
          "request": "launch",
          "module": "issuesuite",
          "args": [
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--updates-json",
            "agent_updates.json",
            "--apply"
          ],
          "console": "integratedTerminal",
          "justMyCode": false
        }
      ]
    }
    """
).lstrip()

VSCODE_CONFIG_SCHEMA_TEMPLATE = textwrap.dedent(
    """
    {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "title": "IssueSuite configuration",
      "type": "object",
      "required": [
        "version",
        "source"
      ],
      "properties": {
        "version": {
          "type": "integer",
          "minimum": 1
        },
        "source": {
          "type": "object",
          "required": [
            "file"
          ],
          "properties": {
            "file": {
              "type": "string"
            },
            "id_pattern": {
              "type": "string"
            },
            "milestone_required": {
              "type": "boolean"
            },
            "milestone_pattern": {
              "type": "string"
            }
          },
          "additionalProperties": true
        },
        "behavior": {
          "type": "object",
          "properties": {
            "dry_run_default": {
              "type": "boolean"
            },
            "truncate_body_diff": {
              "type": "integer",
              "minimum": 0
            },
            "emit_change_events": {
              "type": "boolean"
            }
          },
          "additionalProperties": true
        },
        "defaults": {
          "type": "object",
          "properties": {
            "ensure_labels_enabled": {
              "type": "boolean"
            },
            "ensure_milestones_enabled": {
              "type": "boolean"
            },
            "inject_labels": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          "additionalProperties": true
        },
        "output": {
          "type": "object",
          "properties": {
            "summary_json": {
              "type": "string"
            },
            "plan_json": {
              "type": "string"
            },
            "export_json": {
              "type": "string"
            },
            "mapping_file": {
              "type": "string"
            },
            "hash_state_file": {
              "type": "string"
            },
            "report_html": {
              "type": "string"
            }
          },
          "additionalProperties": true
        },
        "ai": {
          "type": "object",
          "properties": {
            "schema_export_file": {
              "type": "string"
            },
            "schema_summary_file": {
              "type": "string"
            },
            "schema_ai_context_file": {
              "type": "string"
            },
            "schema_version": {
              "type": [
                "string",
                "number"
              ]
            }
          },
          "additionalProperties": true
        },
        "github": {
          "type": "object",
          "properties": {
            "repo": {
              "type": "string"
            },
            "app": {
              "type": "object",
              "properties": {
                "enabled": {
                  "type": "boolean"
                },
                "id": {
                  "type": [
                    "string",
                    "integer"
                  ]
                },
                "private_key": {
                  "type": "string"
                },
                "installation_id": {
                  "type": [
                    "string",
                    "integer"
                  ]
                }
              },
              "additionalProperties": true
            },
            "project": {
              "type": "object",
              "properties": {
                "enable": {
                  "type": "boolean"
                },
                "number": {
                  "type": "integer"
                },
                "field_mappings": {
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  }
                }
              },
              "additionalProperties": true
            }
          },
          "additionalProperties": true
        },
        "logging": {
          "type": "object",
          "properties": {
            "level": {
              "type": "string"
            },
            "json_enabled": {
              "type": "boolean"
            }
          },
          "additionalProperties": true
        },
        "concurrency": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "max_workers": {
              "type": "integer",
              "minimum": 1
            }
          },
          "additionalProperties": true
        },
        "telemetry": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "store_path": {
              "type": "string"
            }
          },
          "additionalProperties": true
        },
        "environment": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "load_dotenv": {
              "type": "boolean"
            },
            "dotenv_path": {
              "type": "string"
            }
          },
          "additionalProperties": true
        },
        "extensions": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "disabled": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          "additionalProperties": true
        },
        "performance": {
          "type": "object",
          "properties": {
            "benchmarking": {
              "type": "boolean"
            }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": true
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
        "./issue_suite.config.schema.json": [
          "issue_suite.config.yaml",
          "**/.issuesuite/**/*.yaml"
        ],
        "https://json.schemastore.org/github-workflow.json": [
          ".github/workflows/*.yml",
          ".github/workflows/*.yaml"
        ]
      },
      "json.schemas": [
        {
          "fileMatch": [
            "issues_export.json"
          ],
          "url": "${workspaceFolder}/issue_export.schema.json"
        },
        {
          "fileMatch": [
            "issues_summary.json"
          ],
          "url": "${workspaceFolder}/issue_change_summary.schema.json"
        },
        {
          "fileMatch": [
            "ai_context.json",
            ".issuesuite/**/*.json"
          ],
          "url": "${workspaceFolder}/ai_context.schema.json"
        }
      ],
      "files.watcherExclude": {
        "**/.issuesuite/**": true
      },
      "search.exclude": {
        "**/.issuesuite/**": true,
        "issues_summary.json": true,
        "issues_plan.json": true,
        "issues_export.json": true,
        "issue_export.schema.json": true,
        "issue_change_summary.schema.json": true,
        "ai_context.schema.json": true,
        "ai_context.json": true,
        "projects_status_report.json": true,
        "projects_status_comment.md": true
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
    updated: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    needs_update: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class EditorAssetTemplate:
    """Template metadata for editor automation assets."""

    path: str
    template: str
    fmt: str = "text"

    def normalized(self) -> str:
        return _normalize_content(self.template, fmt=self.fmt)


def _write_if_needed(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _normalize_content(content: str, *, fmt: str) -> str:
    if fmt == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise ValueError("invalid json") from exc
        normalized = json.dumps(data, indent=2)
        if not normalized.endswith("\n"):
            normalized = f"{normalized}\n"
        return normalized
    return content


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


_VSCODE_ASSET_TEMPLATES: dict[str, EditorAssetTemplate] = {
    "tasks": EditorAssetTemplate(
        path=".vscode/tasks.json",
        template=VSCODE_TASKS_TEMPLATE,
        fmt="json",
    ),
    "launch": EditorAssetTemplate(
        path=".vscode/launch.json",
        template=VSCODE_LAUNCH_TEMPLATE,
        fmt="json",
    ),
    "settings": EditorAssetTemplate(
        path=".vscode/settings.json",
        template=VSCODE_SETTINGS_TEMPLATE,
        fmt="json",
    ),
    "config_schema": EditorAssetTemplate(
        path=".vscode/issue_suite.config.schema.json",
        template=VSCODE_CONFIG_SCHEMA_TEMPLATE,
        fmt="json",
    ),
}

_DEFAULT_VSCODE_ASSETS: tuple[str, ...] = ("tasks", "launch", "settings", "config_schema")


_AssetStatus = Literal["created", "updated", "unchanged", "needs_update"]


def _sync_single_asset(
    target: Path,
    normalized_template: str,
    *,
    fmt: str,
    force: bool,
) -> _AssetStatus:
    if not target.exists():
        _write_if_needed(target, normalized_template, force=True)
        return "created"

    try:
        existing = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        if force:
            _write_if_needed(target, normalized_template, force=True)
            return "updated"
        return "needs_update"

    try:
        normalized_existing = _normalize_content(existing, fmt=fmt)
    except ValueError:
        if force:
            _write_if_needed(target, normalized_template, force=True)
            return "updated"
        return "needs_update"

    if normalized_existing == normalized_template:
        if force and existing != normalized_template:
            _write_if_needed(target, normalized_template, force=True)
            return "updated"
        return "unchanged"

    if force:
        _write_if_needed(target, normalized_template, force=True)
        return "updated"

    return "needs_update"


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
    updated: list[Path] = []
    unchanged: list[Path] = []
    needs_update: list[Path] = []

    for asset in selected:
        template_info = _VSCODE_ASSET_TEMPLATES.get(asset)
        if not template_info:
            continue
        rel_path = template_info.path
        normalized_template = template_info.normalized()
        target = (directory / rel_path).resolve()
        status = _sync_single_asset(
            target,
            normalized_template,
            fmt=template_info.fmt,
            force=force,
        )
        if status == "created":
            created.append(target)
        elif status == "updated":
            updated.append(target)
        elif status == "unchanged":
            skipped.append(target)
            unchanged.append(target)
        else:  # "needs_update"
            skipped.append(target)
            needs_update.append(target)

    return ScaffoldResult(
        created=created,
        skipped=skipped,
        updated=updated,
        unchanged=unchanged,
        needs_update=needs_update,
    )


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
    updated: list[Path] = []
    unchanged: list[Path] = []
    needs_update: list[Path] = []

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
        updated.extend(vscode_result.updated)
        unchanged.extend(vscode_result.unchanged)
        needs_update.extend(vscode_result.needs_update)
    filtered_extras = [item for item in extras if item != "vscode"]
    for rel_path, template, _label in _iter_optional_templates(filtered_extras):
        target = directory / rel_path
        if _write_if_needed(target, template, force):
            created.append(target)
        else:
            skipped.append(target)

    return ScaffoldResult(
        created=created,
        skipped=skipped,
        updated=updated,
        unchanged=unchanged,
        needs_update=needs_update,
    )


__all__ = [
    "scaffold_project",
    "ScaffoldResult",
    "write_vscode_tasks",
    "write_vscode_assets",
]
