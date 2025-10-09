from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from issuesuite.github_projects_sync import (
    ProjectsSyncError,
    build_config,
    sync_projects,
)


def test_build_config_defaults_and_mapping() -> None:
    config = build_config(
        owner=None,
        project_number=None,
        owner_type=None,
        item_title=None,
        status_field=None,
        status_mapping=["on_track=Green", "off_track=Red"],
        coverage_field=None,
        summary_field=None,
        comment_repo=None,
        comment_issue=None,
        token=None,
    )

    assert config.item_title == "IssueSuite Health"
    assert config.status_field == "Status"
    assert config.status_mapping["on_track"] == "Green"
    assert config.status_mapping["off_track"] == "Red"


def test_sync_projects_dry_run_preview(tmp_path: Path) -> None:
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        textwrap.dedent(
            """
            # Next Steps

            ## Tasks

            - [ ] **Owner:** Maintainers (Due: 2025-10-20) — Enable dashboards
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    coverage_payload = tmp_path / "coverage_projects_payload.json"
    coverage_payload.write_text(
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

    config = build_config(
        owner="acme",
        project_number=7,
        owner_type="organization",
        item_title="IssueSuite Health",
        status_field="Status",
        status_mapping=None,
        coverage_field="Coverage %",
        summary_field="Summary",
        comment_repo="acme/repo",
        comment_issue=42,
        token=None,
    )

    result = sync_projects(
        config=config,
        next_steps_paths=[next_steps_path],
        coverage_payload_path=coverage_payload,
        apply=False,
    )

    assert result["project"]["enabled"] is True
    assert result["project"]["dry_run"] is True
    assert result["project"]["status"] == "on_track"
    assert "Frontier Apex status" in result["comment"]
    assert result["comment_result"]["enabled"] is True


def test_sync_projects_apply_requires_token(tmp_path: Path) -> None:
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(
        textwrap.dedent(
            """
            # Next Steps

            ## Tasks

            - [ ] Item
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    coverage_payload = tmp_path / "coverage_projects_payload.json"
    coverage_payload.write_text(json.dumps({"status": "on_track"}), encoding="utf-8")

    config = build_config(
        owner="acme",
        project_number=1,
        owner_type="organization",
        item_title=None,
        status_field="Status",
        status_mapping=None,
        coverage_field=None,
        summary_field=None,
        comment_repo=None,
        comment_issue=None,
        token=None,
    )

    with pytest.raises(ProjectsSyncError):
        sync_projects(
            config=config,
            next_steps_paths=[next_steps_path],
            coverage_payload_path=coverage_payload,
            apply=True,
        )
