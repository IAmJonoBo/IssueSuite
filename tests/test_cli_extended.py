import json
import os
import textwrap
from datetime import date
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet

from issuesuite import cli
from issuesuite.cli import main
from issuesuite.dependency_audit import AllowlistedAdvisory, Finding, SuppressedFinding
from issuesuite.github_issues import IssuesClient

SAMPLE_ISSUES = textwrap.dedent(
    """\
## [slug: extended-alpha]
```yaml
title: Extended Alpha
labels: [alpha]
milestone: "M1: Real-Time Foundation"
status: open
body: |
  Alpha body
```

## [slug: extended-beta]
```yaml
title: Extended Beta
labels: [beta]
milestone: "M2: Performance & Validation"
status: closed
body: |
  Beta body
```
"""
)


CONFIG_WITH_REPO = textwrap.dedent(
    """\
version: 1
source:
  file: ISSUES.md
  id_pattern: "^[a-z0-9][a-z0-9-_]*$"
defaults:
  inject_labels: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
behavior:
  truncate_body_diff: 50
ai:
  schema_export_file: issue_export.schema.json
  schema_summary_file: issue_change_summary.schema.json
  schema_version: 1
github:
  repo: acme/widgets
"""
)


CONFIG_NO_REPO = textwrap.dedent(
    """\
version: 1
source:
  file: ISSUES.md
  id_pattern: "^[a-z0-9][a-z0-9-_]*$"
defaults:
  inject_labels: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
behavior:
  truncate_body_diff: 50
ai:
  schema_export_file: issue_export.schema.json
  schema_summary_file: issue_change_summary.schema.json
  schema_version: 1
"""
)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(CONFIG_WITH_REPO)
    return tmp_path


def test_cli_ai_context_writes_file_and_configures_telemetry(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx_path = fixture_repo / "ai_context.json"
    telemetry_calls: dict[str, object] = {}

    def _fake_configure(**kwargs: object) -> None:
        telemetry_calls.update(kwargs)

    monkeypatch.setenv("ISSUESUITE_OTEL_EXPORTER", "console")
    monkeypatch.setenv("ISSUESUITE_SERVICE_NAME", "issuesuite-tests")
    monkeypatch.setenv("ISSUESUITE_OTEL_ENDPOINT", "http://otel.local")
    monkeypatch.setattr("issuesuite.cli.configure_telemetry", _fake_configure)

    rc = main(
        [
            "ai-context",
            "--config",
            str(fixture_repo / "issue_suite.config.yaml"),
            "--preview",
            "1",
            "--output",
            str(ctx_path),
        ]
    )

    assert rc == 0
    assert telemetry_calls["exporter"] == "console"

    doc = json.loads(ctx_path.read_text())
    assert doc["spec_count"] == 2
    assert len(doc["preview"]) == 1


def test_cli_import_generates_markdown_with_unique_slugs(
    fixture_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample_issues = [
        {
            "title": "Alpha Launch",
            "body": "Alpha body",
            "labels": [{"name": "bug"}],
            "milestone": {"title": "Sprint 1"},
            "state": "open",
        },
        {
            "title": "Alpha Launch",
            "body": "",
            "labels": [],
            "milestone": None,
            "state": "open",
        },
        {
            "title": "Beta Work",
            "body": "Beta body",
            "labels": ["beta"],
            "milestone": {"title": "Sprint 2"},
            "state": "closed",
        },
    ]

    monkeypatch.setattr(IssuesClient, "list_existing", lambda self: sample_issues)

    output_path = fixture_repo / "imported.md"
    rc = main(
        [
            "import",
            "--config",
            str(fixture_repo / "issue_suite.config.yaml"),
            "--output",
            str(output_path),
            "--limit",
            "2",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "[import] wrote 2 issues" in captured.out
    assert "(truncated to 2" in captured.out

    content = output_path.read_text()
    assert "slug: alpha-launch" in content
    assert "slug: alpha-launch-2" in content


def test_cli_reconcile_detects_drift(
    fixture_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(IssuesClient, "list_existing", lambda self: [])

    rc = main(
        [
            "reconcile",
            "--config",
            str(fixture_repo / "issue_suite.config.yaml"),
            "--limit",
            "10",
        ]
    )

    assert rc == 2
    captured = capsys.readouterr()
    assert "[reconcile] Drift items" in captured.out
    assert "spec_only" in captured.out


def test_cli_setup_vscode_scaffolds_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = main(["setup", "--vscode"])

    assert rc == 0

    tasks_path = tmp_path / ".vscode" / "tasks.json"
    launch_path = tmp_path / ".vscode" / "launch.json"
    settings_path = tmp_path / ".vscode" / "settings.json"
    config_schema_path = tmp_path / ".vscode" / "issue_suite.config.schema.json"

    assert tasks_path.exists()
    assert launch_path.exists()
    assert settings_path.exists()
    assert config_schema_path.exists()

    task_data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert task_data["version"] == "2.0.0"
    labels = {task["label"] for task in task_data["tasks"]}
    assert {
        "IssueSuite: Dry-run Sync",
        "IssueSuite: Validate",
        "IssueSuite: Agent Apply (dry-run)",
        "IssueSuite: Schema Bundle",
        "IssueSuite: Security Audit (Offline)",
    }.issubset(labels)

    launch_data = json.loads(launch_path.read_text(encoding="utf-8"))
    assert launch_data["version"] == "0.2.0"
    configurations = launch_data["configurations"]
    assert any(cfg.get("module") == "issuesuite" for cfg in configurations)
    config_names = {cfg["name"] for cfg in configurations}
    assert {
        "IssueSuite: Dry-run Sync",
        "IssueSuite: Full Sync",
        "IssueSuite: Guided Setup",
    }.issubset(config_names)
    dry_run_cfg = next(cfg for cfg in configurations if cfg["name"] == "IssueSuite: Dry-run Sync")
    assert dry_run_cfg.get("preLaunchTask") == "IssueSuite: Validate"

    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings_data["python.defaultInterpreterPath"] == "${workspaceFolder}/.venv/bin/python"
    assert "yaml.schemas" in settings_data
    assert "./issue_suite.config.schema.json" in settings_data["yaml.schemas"]
    schema_mappings = {
        entry["url"]: set(entry["fileMatch"]) for entry in settings_data.get("json.schemas", [])
    }
    assert "${workspaceFolder}/issue_export.schema.json" in schema_mappings
    assert "issues_export.json" in schema_mappings["${workspaceFolder}/issue_export.schema.json"]
    assert "${workspaceFolder}/ai_context.schema.json" in schema_mappings
    assert {
        "ai_context.json",
        ".issuesuite/**/*.json",
    } == schema_mappings["${workspaceFolder}/ai_context.schema.json"]

    first_run_output = capsys.readouterr().out
    assert "[setup] created .vscode/tasks.json" in first_run_output
    assert "[setup] created .vscode/launch.json" in first_run_output
    assert "[setup] created .vscode/settings.json" in first_run_output
    assert "[setup] created .vscode/issue_suite.config.schema.json" in first_run_output

    rc = main(["setup", "--vscode"])

    assert rc == 0

    second_run_output = capsys.readouterr().out
    assert "[setup] already current .vscode/tasks.json" in second_run_output
    assert "[setup] already current .vscode/launch.json" in second_run_output
    assert "[setup] already current .vscode/settings.json" in second_run_output
    assert "[setup] already current .vscode/issue_suite.config.schema.json" in second_run_output
    assert "[setup] no VS Code files created or changed" in second_run_output


def test_cli_setup_vscode_force_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["setup", "--vscode"]) == 0
    capsys.readouterr()

    tasks_path = tmp_path / ".vscode" / "tasks.json"
    tasks_path.write_text("{}", encoding="utf-8")

    assert main(["setup", "--vscode"]) == 0
    second_output = capsys.readouterr().out
    assert "[setup] differs from template .vscode/tasks.json" in second_output
    assert "Run 'issuesuite setup --vscode --force'" in second_output
    assert tasks_path.read_text(encoding="utf-8") == "{}"

    assert main(["setup", "--vscode", "--force"]) == 0
    forced_output = capsys.readouterr().out
    assert "[setup] updated .vscode/tasks.json" in forced_output

    task_data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert task_data["version"] == "2.0.0"


def test_cli_setup_vscode_handles_reformatted_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["setup", "--vscode"]) == 0
    capsys.readouterr()

    tasks_path = tmp_path / ".vscode" / "tasks.json"
    canonical = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks_path.write_text(json.dumps(canonical), encoding="utf-8")

    assert main(["setup", "--vscode"]) == 0
    rerun_output = capsys.readouterr().out
    assert "[setup] already current .vscode/tasks.json" in rerun_output
    assert "[setup] no VS Code files created or changed" in rerun_output

def test_cli_doctor_reports_warnings_and_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(CONFIG_NO_REPO)

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    rc = main(
        [
            "doctor",
            "--config",
            str(tmp_path / "issue_suite.config.yaml"),
        ]
    )

    assert rc == 2
    captured = capsys.readouterr()
    assert "[doctor] repo: None" in captured.out
    assert "mock mode detected" in captured.out
    # Accept either old or new format
    assert "[doctor] warnings" in captured.out or "warning(s) detected" in captured.out
    assert "[doctor] problems" in captured.out or "problem(s) detected" in captured.err


def test_cli_security_offline(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["security", "--offline-only"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "No known vulnerabilities detected." in captured.out


def test_cli_security_refresh_offline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    invoked: dict[str, bool] = {}

    def _refresh() -> None:
        invoked["called"] = True

    monkeypatch.setattr("issuesuite.cli.refresh_advisories", _refresh)
    rc = main(["security", "--offline-only", "--refresh-offline"])
    captured = capsys.readouterr()

    assert rc == 0
    assert invoked.get("called") is True
    assert "No known vulnerabilities detected." in captured.out


def test_cli_security_scopes_disable_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    marker: dict[str, object] = {}

    def _fake_run(args):
        marker["args"] = args
        marker["env"] = os.environ.get("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE")
        return 0

    monkeypatch.setattr("issuesuite.cli.run_resilient_pip_audit", _fake_run)
    monkeypatch.delenv("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE", raising=False)

    rc = main(["security", "--offline-only", "--pip-audit", "--pip-audit-disable-online"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "No known vulnerabilities detected." in captured.out
    assert marker["env"] == "1"
    assert os.environ.get("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE") is None
    assert marker["args"][-1] == "--strict"


def test_cli_security_reports_allowlisted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    finding = Finding(
        package="pip",
        installed_version="25.2",
        vulnerability_id="GHSA-4xh5-x5gv-qwph",
        description="",
        fixed_versions=(),
        source="pip-audit",
    )
    allow = AllowlistedAdvisory(
        package="pip",
        vulnerability_id="GHSA-4xh5-x5gv-qwph",
        specifiers=SpecifierSet("<=25.2"),
        reason="Awaiting upstream fix",
        expires=date.today(),
        owner="Maintainers",
        reference="https://github.com/advisories/GHSA-4xh5-x5gv-qwph",
    )
    suppressed = SuppressedFinding(finding=finding, allowlisted=allow)

    monkeypatch.setattr(
        "issuesuite.cli.run_dependency_audit",
        lambda advisories, packages, online_probe=True, online_collector=None: (
            [finding],
            None,
        ),
    )
    monkeypatch.setattr("issuesuite.cli.load_security_allowlist", lambda: [allow])
    monkeypatch.setattr(
        "issuesuite.cli.apply_security_allowlist",
        lambda findings, allowlist: ([], [suppressed]),
    )

    rc = main(["security", "--offline-only"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "Allowlisted vulnerabilities detected" in captured.err
    assert "pip GHSA-4xh5-x5gv-qwph" in captured.err


def test_cli_projects_status_generates_artifacts(tmp_path: Path) -> None:
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        """# Next Steps

## Tasks

- [ ] **Owner:** Maintainers (Due: 2025-10-15) — Automate dashboards
- [x] **Owner:** Assistant (Due: 2025-10-01) — Ship telemetry exporter

## Steps
- placeholder
""",
        encoding="utf-8",
    )
    coverage_path = tmp_path / "coverage_projects_payload.json"
    coverage_path.write_text(
        json.dumps(
            {
                "status": "on_track",
                "emoji": "✅",
                "message": "Coverage 87% (target 85%)",
            }
        ),
        encoding="utf-8",
    )
    json_output = tmp_path / "projects_status.json"
    comment_output = tmp_path / "projects_status.md"

    rc = main(
        [
            "projects-status",
            "--next-steps",
            str(next_steps_path),
            "--coverage",
            str(coverage_path),
            "--output",
            str(json_output),
            "--comment-output",
            str(comment_output),
            "--lookahead-days",
            "10",
        ]
    )

    assert rc == 0
    payload = json.loads(json_output.read_text())
    assert payload["status"] == "at_risk"
    assert payload["tasks"]["open_count"] == 1
    assert payload["tasks"]["due_soon_count"] == 1
    comment = comment_output.read_text()
    assert "Frontier Apex status" in comment
    assert "Automate dashboards" in comment


def test_cli_projects_sync_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        """# Next Steps

## Tasks

- [ ] **Owner:** Maintainers (Due: 2025-10-20) — Enable dashboards
""",
        encoding="utf-8",
    )
    coverage_path = tmp_path / "coverage_projects_payload.json"
    coverage_path.write_text(
        json.dumps(
            {
                "status": "on_track",
                "emoji": "✅",
                "message": "Coverage 90% (target 85%)",
                "overall_coverage": 0.9,
            }
        ),
        encoding="utf-8",
    )
    comment_output = tmp_path / "projects_sync_comment.md"

    rc = main(
        [
            "projects-sync",
            "--next-steps",
            str(next_steps_path),
            "--coverage",
            str(coverage_path),
            "--project-owner",
            "acme",
            "--project-number",
            "7",
            "--status-field",
            "Status",
            "--coverage-field",
            "Coverage %",
            "--summary-field",
            "Summary",
            "--comment-repo",
            "acme/repo",
            "--comment-issue",
            "42",
            "--comment-output",
            str(comment_output),
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "Frontier Apex status" in captured.out
    assert "dry-run preview" in captured.err
    assert "Frontier Apex status" in comment_output.read_text()


def test_cli_projects_sync_writes_plan_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text("# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8")
    coverage_path = tmp_path / "coverage_projects_payload.json"
    coverage_path.write_text(
        json.dumps({"status": "on_track", "overall_coverage": 0.92}),
        encoding="utf-8",
    )
    plan_output = tmp_path / "projects_sync_plan.json"

    rc = main(
        [
            "projects-sync",
            "--next-steps",
            str(next_steps_path),
            "--coverage",
            str(coverage_path),
            "--project-owner",
            "acme",
            "--project-number",
            "7",
            "--status-field",
            "Status",
            "--plan-output",
            str(plan_output),
        ]
    )

    assert rc == 0
    payload = json.loads(plan_output.read_text())
    assert payload["status"] == "on_track"
    assert "Frontier Apex status" in capsys.readouterr().out


def test_cli_projects_status_respects_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        textwrap.dedent(
            """
            # Next Steps

            ## Tasks

            - [ ] **Owner:** Maintainers — Follow up
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    rc = main(
        [
            "--quiet",
            "projects-status",
            "--next-steps",
            str(next_steps_path),
            "--output",
            str(tmp_path / "projects_status.json"),
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_cli_projects_sync_apply_requires_token(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text("# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8")
    coverage_path = tmp_path / "coverage_projects_payload.json"
    coverage_path.write_text(json.dumps({"status": "on_track"}), encoding="utf-8")

    rc = main(
        [
            "projects-sync",
            "--next-steps",
            str(next_steps_path),
            "--coverage",
            str(coverage_path),
            "--project-owner",
            "acme",
            "--project-number",
            "7",
            "--status-field",
            "Status",
            "--apply",
        ]
    )

    assert rc == 1
    captured = capsys.readouterr()
    assert "token required" in captured.err


def test_cli_projects_sync_uses_config_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "issue_suite.config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            version: 1
            source:
              file: ISSUES.md
            github:
              repo: acme/example
              project:
                enable: true
                number: 7
                field_mappings:
                  status: Status
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        textwrap.dedent(
            """
            # Next Steps

            ## Tasks

            - [ ] **Owner:** Maintainers — Follow up
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    captured_config: dict[str, object] = {}

    original_build = cli.build_projects_sync_config
    original_sync = cli.sync_projects

    def fake_build_config(**kwargs: object) -> object:
        captured_config.update(kwargs)
        return original_build(**kwargs)

    def fake_sync_projects(**kwargs: object) -> dict[str, object]:
        captured_config["sync_kwargs"] = kwargs
        return {
            "comment": "✅ Frontier Apex status: on_track\n",
            "project": {"enabled": True, "updated": False, "status": "on_track"},
            "comment_result": {"enabled": False},
            "report": {"status": "on_track", "message": "ok"},
        }

    monkeypatch.setattr(cli, "build_projects_sync_config", fake_build_config)
    monkeypatch.setattr(cli, "sync_projects", fake_sync_projects)

    rc = main(
        [
            "projects-sync",
            "--config",
            str(config_path),
            "--next-steps",
            str(next_steps_path),
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "Frontier Apex status" in captured.out
    assert "dry-run preview" in captured.err
    assert captured_config["owner"] == "acme"
    assert captured_config["project_number"] == 7
    assert captured_config["status_field"] == "Status"
