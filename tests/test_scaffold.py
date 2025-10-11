from __future__ import annotations

import json
from pathlib import Path

from issuesuite.scaffold import scaffold_project, write_vscode_assets


def test_scaffold_project_creates_core_files(tmp_path: Path) -> None:
    result = scaffold_project(tmp_path, issues_filename="backlog.md")

    config_path = tmp_path / "issue_suite.config.yaml"
    issues_path = tmp_path / "backlog.md"

    assert config_path in result.created
    assert issues_path in result.created

    config_text = config_path.read_text(encoding="utf-8")
    assert "file: backlog.md" in config_text
    assert "summary_json: issues_summary.json" in config_text

    issues_text = issues_path.read_text(encoding="utf-8")
    assert "## [slug: example-task]" in issues_text


def test_scaffold_project_handles_extras_and_skips(tmp_path: Path) -> None:
    config_path = tmp_path / "issue_suite.config.yaml"
    config_path.write_text("existing", encoding="utf-8")

    result = scaffold_project(
        tmp_path,
        include=["workflow", "vscode", "gitignore", "unknown"],
        force=False,
    )

    assert config_path in result.skipped

    workflow_path = tmp_path / ".github/workflows/issuesuite-sync.yml"
    tasks_path = tmp_path / ".vscode/tasks.json"
    launch_path = tmp_path / ".vscode/launch.json"
    settings_path = tmp_path / ".vscode/settings.json"
    schema_path = tmp_path / ".vscode/issue_suite.config.schema.json"
    gitignore_path = tmp_path / ".gitignore"

    for path in (
        workflow_path,
        tasks_path,
        launch_path,
        settings_path,
        schema_path,
        gitignore_path,
    ):
        assert path in result.created
        assert path.exists()

    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    assert ".issuesuite/" in gitignore_text

    schema_text = schema_path.read_text(encoding="utf-8")
    assert "IssueSuite configuration" in schema_text


def test_scaffold_project_force_overwrites(tmp_path: Path) -> None:
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text("old", encoding="utf-8")

    result = scaffold_project(tmp_path, issues_filename="ISSUES.md", force=True)

    assert issues_path in result.created
    assert "## [slug: example-task]" in issues_path.read_text(encoding="utf-8")


def test_write_vscode_assets_detects_drift(tmp_path: Path) -> None:
    tasks_path = tmp_path / ".vscode" / "tasks.json"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text("{}", encoding="utf-8")

    result = write_vscode_assets(tmp_path, assets=("tasks",))
    assert tasks_path in result.needs_update
    assert tasks_path in result.skipped

    forced = write_vscode_assets(tmp_path, assets=("tasks",), force=True)
    assert tasks_path in forced.updated
    assert tasks_path not in forced.needs_update


def test_write_vscode_assets_accepts_reformatted_json(tmp_path: Path) -> None:
    tasks_path = tmp_path / ".vscode" / "tasks.json"

    initial = write_vscode_assets(tmp_path, assets=("tasks",))
    assert tasks_path in initial.created

    canonical_data = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks_path.write_text(json.dumps(canonical_data), encoding="utf-8")

    rerun = write_vscode_assets(tmp_path, assets=("tasks",))
    assert tasks_path in rerun.unchanged
    assert tasks_path in rerun.skipped

    forced = write_vscode_assets(tmp_path, assets=("tasks",), force=True)
    assert tasks_path in forced.updated
    normalized_text = tasks_path.read_text(encoding="utf-8")
    assert normalized_text.endswith("\n")
    assert json.loads(normalized_text)["version"] == "2.0.0"
