from __future__ import annotations

from pathlib import Path

from issuesuite.scaffold import scaffold_project


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
    gitignore_path = tmp_path / ".gitignore"

    for path in (workflow_path, tasks_path, launch_path, settings_path, gitignore_path):
        assert path in result.created
        assert path.exists()

    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    assert ".issuesuite/" in gitignore_text


def test_scaffold_project_force_overwrites(tmp_path: Path) -> None:
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text("old", encoding="utf-8")

    result = scaffold_project(tmp_path, issues_filename="ISSUES.md", force=True)

    assert issues_path in result.created
    assert "## [slug: example-task]" in issues_path.read_text(encoding="utf-8")
