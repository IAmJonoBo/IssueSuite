import json
from importlib import resources
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from issuesuite.bootstrap import bootstrap_project, ensure_vscode_tasks


def test_bootstrap_project_creates_and_skips(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "issue_suite.config.yaml"

    result = bootstrap_project(
        config_path,
        force=False,
        include_vscode=True,
        include_workflow=True,
    )

    assert config_path.exists()
    assert (tmp_path / "ISSUES.md").exists()
    assert (tmp_path / "agent_updates.json").exists()
    assert (tmp_path / ".github/workflows/issuesuite.yml").exists()
    assert (tmp_path / ".vscode/tasks.json").exists()

    assert set(result.created) == {
        config_path,
        Path("ISSUES.md"),
        Path("agent_updates.json"),
        Path(".github/workflows/issuesuite.yml"),
        Path(".vscode/tasks.json"),
    }
    assert result.skipped == []
    assert result.merged == []

    rerun = bootstrap_project(
        config_path,
        force=False,
        include_vscode=True,
        include_workflow=True,
    )

    assert rerun.created == []
    assert rerun.merged == []
    assert set(rerun.skipped) == {
        config_path,
        Path("ISSUES.md"),
        Path("agent_updates.json"),
        Path(".github/workflows/issuesuite.yml"),
        Path(".vscode/tasks.json"),
    }

    # Forcing should rewrite core assets even if they were modified.
    (tmp_path / "ISSUES.md").write_text("changed", encoding="utf-8")
    config_path.write_text("changed", encoding="utf-8")
    (tmp_path / "agent_updates.json").write_text("{}", encoding="utf-8")

    forced = bootstrap_project(
        config_path,
        force=True,
        include_vscode=False,
        include_workflow=False,
    )

    assert set(forced.created) == {config_path, Path("ISSUES.md"), Path("agent_updates.json")}
    assert forced.skipped == []
    assert forced.merged == []
    assert "changed" not in (tmp_path / "ISSUES.md").read_text(encoding="utf-8")
    assert "changed" not in config_path.read_text(encoding="utf-8")


def test_ensure_vscode_tasks_merges_and_force(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    tasks_path = tmp_path / ".vscode/tasks.json"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {
        "version": "2.0.0",
        "tasks": [
            {"label": "Custom Task"},
            {"label": "IssueSuite: Validate"},
        ],
    }
    tasks_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    result = ensure_vscode_tasks(force=False)
    assert result.created == []
    assert result.skipped == []
    assert result.merged == [Path(".vscode/tasks.json")]

    template = json.loads(
        resources.files("issuesuite.templates.bootstrap")
        .joinpath("vscode_tasks.json")
        .read_text(encoding="utf-8")
    )
    data = json.loads(tasks_path.read_text(encoding="utf-8"))

    template_labels = {task["label"] for task in template["tasks"]}
    labels = [task.get("label") for task in data.get("tasks", [])]
    assert template_labels <= set(labels)
    assert "Custom Task" in labels
    assert labels.count("IssueSuite: Validate") == 1

    tasks_path.write_text("{}", encoding="utf-8")
    forced = ensure_vscode_tasks(force=True)
    assert forced.created == [Path(".vscode/tasks.json")]
    assert forced.skipped == []
    assert forced.merged == []

    forced_data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert forced_data == template
