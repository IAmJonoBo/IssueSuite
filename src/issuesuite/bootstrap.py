"""Bootstrap helpers for IssueSuite setup automation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

TEMPLATE_PACKAGE = "issuesuite.templates.bootstrap"

__all__ = [
    "BootstrapResult",
    "bootstrap_project",
    "ensure_agent_updates_sample",
    "ensure_github_workflow",
    "ensure_issue_suite_config",
    "ensure_issues_md",
    "ensure_vscode_tasks",
]


def _template_text(filename: str) -> str:
    template_file = resources.files(TEMPLATE_PACKAGE).joinpath(filename)
    return template_file.read_text(encoding="utf-8")


def _write_file(path: Path, contents: str, *, force: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return False
    if not contents.endswith("\n"):
        contents = f"{contents}\n"
    path.write_text(contents, encoding="utf-8")
    return True


def _append_or_write_tasks(
    path: Path, template: dict[str, Any], *, force: bool
) -> tuple[bool, bool]:  # noqa: PLR0912
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized_template = json.dumps(template, indent=2) + "\n"

    if force or not path.exists():
        path.write_text(serialized_template, encoding="utf-8")
        return True, False

    try:
        existing_raw = path.read_text(encoding="utf-8")
        existing_data: Any = json.loads(existing_raw) if existing_raw.strip() else {}
    except json.JSONDecodeError:
        path.write_text(serialized_template, encoding="utf-8")
        return True, False

    if not isinstance(existing_data, dict):
        existing_data = {}

    existing_tasks: list[dict[str, Any]] = []
    for task in existing_data.get("tasks", []):
        if isinstance(task, dict):
            existing_tasks.append(task)
    labels = {
        task.get("label")
        for task in existing_tasks
        if isinstance(task.get("label"), str)
    }

    merged = False
    for task in template.get("tasks", []):
        if not isinstance(task, dict):
            continue
        label = task.get("label")
        if isinstance(label, str) and label in labels:
            continue
        existing_tasks.append(task)
        if isinstance(label, str):
            labels.add(label)
        merged = True

    if not merged:
        return False, False

    existing_data["tasks"] = existing_tasks
    if "version" not in existing_data:
        template_version = template.get("version")
        if isinstance(template_version, str):
            existing_data["version"] = template_version
        else:
            existing_data["version"] = "2.0.0"

    path.write_text(json.dumps(existing_data, indent=2) + "\n", encoding="utf-8")
    return False, True


@dataclass
class BootstrapResult:
    created: list[Path]
    skipped: list[Path]
    merged: list[Path]

    def extend(self, other: BootstrapResult) -> None:
        self.created.extend(other.created)
        self.skipped.extend(other.skipped)
        self.merged.extend(other.merged)

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self.created:
            lines.append(
                "[setup] Created: " + ", ".join(str(path) for path in self.created)
            )
        if self.merged:
            lines.append(
                "[setup] Updated: " + ", ".join(str(path) for path in self.merged)
            )
        if self.skipped:
            lines.append(
                "[setup] Skipped (exists): "
                + ", ".join(str(path) for path in self.skipped)
            )
        if not lines:
            lines.append("[setup] Nothing to do (all assets already present)")
        return lines


def ensure_vscode_tasks(*, force: bool) -> BootstrapResult:
    template = json.loads(_template_text("vscode_tasks.json"))
    path = Path(".vscode/tasks.json")
    written, merged = _append_or_write_tasks(path, template, force=force)

    created_paths: list[Path] = []
    skipped_paths: list[Path] = []
    merged_paths: list[Path] = []
    if written:
        created_paths.append(path)
    elif merged:
        merged_paths.append(path)
    else:
        skipped_paths.append(path)

    return BootstrapResult(
        created=created_paths, skipped=skipped_paths, merged=merged_paths
    )


def ensure_issue_suite_config(config_path: Path, *, force: bool) -> BootstrapResult:
    template = _template_text("issue_suite.config.yaml")
    if _write_file(config_path, template, force=force):
        return BootstrapResult(created=[config_path], skipped=[], merged=[])
    return BootstrapResult(created=[], skipped=[config_path], merged=[])


def ensure_issues_md(*, force: bool) -> BootstrapResult:
    template = _template_text("ISSUES.md")
    path = Path("ISSUES.md")
    if _write_file(path, template, force=force):
        return BootstrapResult(created=[path], skipped=[], merged=[])
    return BootstrapResult(created=[], skipped=[path], merged=[])


def ensure_agent_updates_sample(*, force: bool) -> BootstrapResult:
    template = _template_text("agent_updates.json")
    path = Path("agent_updates.json")
    if _write_file(path, template, force=force):
        return BootstrapResult(created=[path], skipped=[], merged=[])
    return BootstrapResult(created=[], skipped=[path], merged=[])


def ensure_github_workflow(*, force: bool) -> BootstrapResult:
    template = _template_text("github_workflow.yml")
    path = Path(".github/workflows/issuesuite.yml")
    if _write_file(path, template, force=force):
        return BootstrapResult(created=[path], skipped=[], merged=[])
    return BootstrapResult(created=[], skipped=[path], merged=[])


def bootstrap_project(
    config_path: Path,
    *,
    force: bool,
    include_vscode: bool,
    include_workflow: bool,
) -> BootstrapResult:
    created: list[Path] = []
    skipped: list[Path] = []
    merged: list[Path] = []

    for result in (
        ensure_issue_suite_config(config_path, force=force),
        ensure_issues_md(force=force),
        ensure_agent_updates_sample(force=force),
    ):
        created.extend(result.created)
        skipped.extend(result.skipped)
        merged.extend(result.merged)

    if include_vscode:
        vscode_result = ensure_vscode_tasks(force=force)
        created.extend(vscode_result.created)
        skipped.extend(vscode_result.skipped)
        merged.extend(vscode_result.merged)

    if include_workflow:
        workflow_result = ensure_github_workflow(force=force)
        created.extend(workflow_result.created)
        skipped.extend(workflow_result.skipped)
        merged.extend(workflow_result.merged)

    return BootstrapResult(created=created, skipped=skipped, merged=merged)
