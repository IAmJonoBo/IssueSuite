from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

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


@patch("requests.Session")
def test_apply_project_update_with_mocked_http(
    mock_session_class: MagicMock, tmp_path: Path
) -> None:
    """Test _apply_project_update with mocked HTTP requests."""
    # Setup mock session
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock GraphQL responses
    # First call: fetch project metadata
    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "data": {
            "organization": {
                "projectV2": {
                    "id": "PROJECT_123",
                    "title": "Test Project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "FIELD_STATUS",
                                "name": "Status",
                                "dataType": "SINGLE_SELECT",
                                "options": {
                                    "nodes": [
                                        {"id": "OPT_GREEN", "name": "Green"},
                                        {"id": "OPT_RED", "name": "Red"},
                                    ]
                                },
                            },
                            {
                                "id": "FIELD_COVERAGE",
                                "name": "Coverage %",
                                "dataType": "NUMBER",
                            },
                        ]
                    },
                    "items": {"nodes": [{"id": "ITEM_123", "title": "IssueSuite Health"}]},
                }
            }
        }
    }

    # Second call: update project item
    update_response = MagicMock()
    update_response.status_code = 200
    update_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM_123"}}}
    }

    mock_session.post.side_effect = [
        metadata_response,
        update_response,
        update_response,
    ]

    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text("# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8")

    coverage_payload = tmp_path / "coverage_projects_payload.json"
    coverage_payload.write_text(
        json.dumps({"status": "on_track", "overall_coverage": 0.9}),
        encoding="utf-8",
    )

    config = build_config(
        owner="acme",
        project_number=7,
        owner_type="organization",
        item_title="IssueSuite Health",
        status_field="Status",
        status_mapping=["on_track=Green"],
        coverage_field="Coverage %",
        summary_field=None,
        comment_repo=None,
        comment_issue=None,
        token="ghp_test_token",
    )

    result = sync_projects(
        config=config,
        next_steps_paths=[next_steps_path],
        coverage_payload_path=coverage_payload,
        apply=True,
    )

    assert result["project"]["enabled"] is True
    assert result["project"]["dry_run"] is False
    assert mock_session.post.call_count >= 2


@patch("requests.Session")
def test_post_status_comment_with_mocked_http(
    mock_session_class: MagicMock, tmp_path: Path
) -> None:
    """Test _post_status_comment with mocked HTTP requests."""
    # Setup mock session
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock REST API response for comment posting
    comment_response = MagicMock()
    comment_response.status_code = 201
    comment_response.json.return_value = {"id": 123, "body": "Test comment"}

    mock_session.post.side_effect = [comment_response]

    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text("# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8")

    coverage_payload = tmp_path / "coverage_projects_payload.json"
    coverage_payload.write_text(
        json.dumps({"status": "on_track", "message": "All good"}),
        encoding="utf-8",
    )

    # Don't enable project sync, only comment posting
    config = build_config(
        owner=None,  # Disable project sync
        project_number=None,
        owner_type=None,
        item_title=None,
        status_field=None,
        status_mapping=None,
        coverage_field=None,
        summary_field=None,
        comment_repo="acme/repo",
        comment_issue=42,
        token="ghp_test_token",
    )

    result = sync_projects(
        config=config,
        next_steps_paths=[next_steps_path],
        coverage_payload_path=coverage_payload,
        apply=True,
    )

    assert result["comment_result"]["enabled"] is True
    assert result["comment_result"]["dry_run"] is False
    assert result["project"]["enabled"] is False  # Project sync should be disabled


@patch("requests.Session")
def test_error_handling_http_failure(mock_session_class: MagicMock, tmp_path: Path) -> None:
    """Test error handling when HTTP requests fail."""
    # Setup mock session
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock failed GraphQL response
    error_response = MagicMock()
    error_response.status_code = 500
    error_response.text = "Internal Server Error"

    mock_session.post.return_value = error_response

    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text("# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8")

    coverage_payload = tmp_path / "coverage_projects_payload.json"
    coverage_payload.write_text(json.dumps({"status": "on_track"}), encoding="utf-8")

    config = build_config(
        owner="acme",
        project_number=7,
        owner_type="organization",
        item_title="IssueSuite Health",
        status_field="Status",
        status_mapping=None,
        coverage_field=None,
        summary_field=None,
        comment_repo=None,
        comment_issue=None,
        token="ghp_test_token",
    )

    with pytest.raises(ProjectsSyncError):
        sync_projects(
            config=config,
            next_steps_paths=[next_steps_path],
            coverage_payload_path=coverage_payload,
            apply=True,
        )


@patch("requests.Session")
def test_error_handling_missing_field(mock_session_class: MagicMock, tmp_path: Path) -> None:
    """Test error handling when required field is missing from project."""
    # Setup mock session
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    # Mock GraphQL response with missing field
    metadata_response = MagicMock()
    metadata_response.status_code = 200
    metadata_response.json.return_value = {
        "data": {
            "organization": {
                "projectV2": {
                    "id": "PROJECT_123",
                    "title": "Test Project",
                    "fields": {"nodes": []},  # No fields
                    "items": {"nodes": [{"id": "ITEM_123", "title": "IssueSuite Health"}]},
                }
            }
        }
    }

    mock_session.post.return_value = metadata_response

    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text("# Next Steps\n\n## Tasks\n\n- [ ] Item\n", encoding="utf-8")

    coverage_payload = tmp_path / "coverage_projects_payload.json"
    coverage_payload.write_text(json.dumps({"status": "on_track"}), encoding="utf-8")

    config = build_config(
        owner="acme",
        project_number=7,
        owner_type="organization",
        item_title="IssueSuite Health",
        status_field="MissingField",  # This field doesn't exist
        status_mapping=None,
        coverage_field=None,
        summary_field=None,
        comment_repo=None,
        comment_issue=None,
        token="ghp_test_token",
    )

    with pytest.raises(ProjectsSyncError, match="not found"):
        sync_projects(
            config=config,
            next_steps_paths=[next_steps_path],
            coverage_payload_path=coverage_payload,
            apply=True,
        )
