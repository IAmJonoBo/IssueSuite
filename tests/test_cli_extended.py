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
    assert "[doctor] warnings" in captured.out
    assert "[doctor] problems" in captured.out


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

    rc = main(
        ["security", "--offline-only", "--pip-audit", "--pip-audit-disable-online"]
    )
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


def test_cli_projects_sync_apply_requires_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        "# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8"
    )
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
