from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from issuesuite import setup_wizard


class FakeAuthManager:
    def __init__(
        self,
        *,
        token: str | None = None,
        app_config: dict[str, object] | None = None,
        online: bool = True,
        recommendations: list[str] | None = None,
    ) -> None:
        self._token = token
        self._app_config = app_config or {"app_id": None, "private_key": None}
        self._online = online
        self._recommendations = recommendations or []

    def get_github_token(self) -> str | None:
        return self._token

    def get_github_app_config(self) -> dict[str, object]:
        return self._app_config

    def is_online_environment(self) -> bool:
        return self._online

    def get_authentication_recommendations(self) -> list[str]:
        return list(self._recommendations)


@pytest.fixture
def wizard(tmp_path: Path) -> tuple[Path, setup_wizard.GuidedPlan, FakeAuthManager]:
    auth = FakeAuthManager(token=None, online=False)
    plan = setup_wizard.build_guided_plan(auth, root=tmp_path)
    return tmp_path, plan, auth


def test_guided_plan_identifies_missing_assets(
    wizard: tuple[Path, setup_wizard.GuidedPlan, FakeAuthManager],
) -> None:
    _, plan, _ = wizard
    statuses = {check.name: check for check in plan.checks}

    assert statuses["Configuration"].status == setup_wizard.CheckStatus.ACTION
    assert "issue_suite.config.yaml" in statuses["Configuration"].message
    assert statuses["Specifications"].status == setup_wizard.CheckStatus.ACTION
    assert "ISSUES.md" in statuses["Specifications"].message
    assert any("issuesuite init --all-extras" in cmd for cmd in plan.commands)


def test_guided_plan_summarises_coverage(tmp_path: Path) -> None:
    auth = FakeAuthManager(token="ghp_example", online=True)
    config_path = tmp_path / "issue_suite.config.yaml"
    issues_path = tmp_path / "ISSUES.md"
    env_path = tmp_path / ".env"
    vscode_dir = tmp_path / ".vscode"
    summary_path = tmp_path / "coverage_summary.json"
    history_dir = tmp_path / ".issuesuite"
    history_dir.mkdir()

    config_path.write_text("name: demo", encoding="utf-8")
    issues_path.write_text("## [slug: demo]\n```yaml\n```", encoding="utf-8")
    env_path.write_text("GITHUB_TOKEN=ghp_example", encoding="utf-8")
    vscode_dir.mkdir()
    summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2025-10-09T00:00:00+00:00",
                "report": "coverage.xml",
                "modules": [
                    {
                        "module": "src/issuesuite/core.py",
                        "coverage": 0.9,
                        "threshold": 0.9,
                        "meets_threshold": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = setup_wizard.build_guided_plan(auth, root=tmp_path)
    statuses = {check.name: check for check in plan.checks}

    assert statuses["Configuration"].status == setup_wizard.CheckStatus.READY
    assert statuses["Specifications"].status == setup_wizard.CheckStatus.READY
    assert statuses["Coverage Telemetry"].status == setup_wizard.CheckStatus.READY
    assert "90.00%" in statuses["Coverage Telemetry"].message
    assert "python scripts/coverage_trends.py" in plan.follow_ups


def test_render_guided_plan_outputs_ascii_box(tmp_path: Path) -> None:
    auth = FakeAuthManager()
    plan = setup_wizard.build_guided_plan(auth, root=tmp_path)
    buffer = io.StringIO()
    setup_wizard.render_guided_plan(plan, stream=buffer)
    output = buffer.getvalue()
    assert "IssueSuite Guided Setup" in output
    assert "╔" in output and "╚" in output
