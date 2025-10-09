from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock, patch

from _pytest.monkeypatch import MonkeyPatch

from issuesuite.project import (
    GitHubProjectAssigner,
    NoopProjectAssigner,
    ProjectConfig,
    build_project_assigner,
)


class MockIssueSpec:
    def __init__(
        self,
        external_id: str = "001",
        labels: Iterable[str] | None = None,
        milestone: str | None = None,
        status: str | None = None,
    ) -> None:
        self.external_id = external_id
        self.labels: list[str] = list(labels or [])
        self.milestone = milestone
        self.status = status


def test_noop_project_assigner() -> None:
    """Test that NoopProjectAssigner does nothing."""
    assigner = NoopProjectAssigner()
    spec = MockIssueSpec()

    # Should not raise any errors
    assigner.assign(123, spec)


def test_build_project_assigner_disabled() -> None:
    """Test building project assigner when disabled."""
    config = ProjectConfig(enabled=False, number=None, field_mappings={})
    assigner = build_project_assigner(config)

    assert isinstance(assigner, NoopProjectAssigner)


def test_build_project_assigner_enabled() -> None:
    """Test building project assigner when enabled."""
    config = ProjectConfig(enabled=True, number=123, field_mappings={"labels": "Status"})
    assigner = build_project_assigner(config)

    assert isinstance(assigner, GitHubProjectAssigner)
    assert assigner.config.number == 123
    assert assigner.config.field_mappings == {"labels": "Status"}


def test_github_project_assigner_mock_mode(monkeypatch: MonkeyPatch) -> None:
    """Test GitHubProjectAssigner in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(
        enabled=True,
        number=456,
        field_mappings={"labels": "Status", "milestone": "Priority"},
    )
    assigner = GitHubProjectAssigner(config)

    spec = MockIssueSpec(
        external_id="TEST001", labels=["bug", "high-priority"], milestone="Sprint 1"
    )

    # Should not raise errors in mock mode
    assigner.assign(789, spec)
    # If we get here without exceptions, the mock functionality works


def test_github_project_assigner_get_project_id_mock(monkeypatch: MonkeyPatch) -> None:
    """Test getting project ID in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=789, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    project_id = assigner._get_project_id()
    assert project_id == "mock_project_789"

    # Should cache the result
    project_id2 = assigner._get_project_id()
    assert project_id2 == project_id


def test_github_project_assigner_get_project_fields_mock(
    monkeypatch: MonkeyPatch,
) -> None:
    """Test getting project fields in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    fields = assigner._get_project_fields()

    assert "Status" in fields
    assert "Priority" in fields
    assert "Assignee" in fields
    assert fields["Status"]["type"] == "single_select"


def test_github_project_assigner_get_issue_id_mock(monkeypatch: MonkeyPatch) -> None:
    """Test getting issue ID in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    issue_id = assigner._get_issue_id(456)
    assert issue_id == "mock_issue_456"


def test_github_project_assigner_add_issue_to_project_mock(
    monkeypatch: MonkeyPatch,
) -> None:
    """Test adding issue to project in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    item_id = assigner._add_issue_to_project(789)
    assert item_id == "mock_item_789"


def test_github_project_assigner_update_field_mock(monkeypatch: MonkeyPatch) -> None:
    """Test updating project field in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    result = assigner._update_project_field("item_123", "Status", "In Progress")
    assert result is True


def test_github_project_assigner_update_nonexistent_field_mock(
    monkeypatch: MonkeyPatch,
) -> None:
    """Test updating nonexistent project field in mock mode."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    result = assigner._update_project_field("item_123", "NonExistent", "value")
    assert result is False


def test_github_project_assigner_disabled_config() -> None:
    """Test GitHubProjectAssigner with disabled config."""
    config = ProjectConfig(enabled=False, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    spec = MockIssueSpec()

    # Should return early without doing anything
    assigner.assign(456, spec)


def test_github_project_assigner_no_project_number() -> None:
    """Test GitHubProjectAssigner with no project number."""
    config = ProjectConfig(enabled=True, number=None, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    spec = MockIssueSpec()

    # Should return early without doing anything
    assigner.assign(456, spec)


def test_project_field_mapping_with_list_values(monkeypatch: MonkeyPatch) -> None:
    """Test project field mapping when spec has list values (e.g., labels)."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(enabled=True, number=123, field_mappings={"labels": "Status"})
    assigner = GitHubProjectAssigner(config)

    spec = MockIssueSpec(labels=["bug", "enhancement", "high-priority"])

    # Should not raise errors and should handle list values properly
    assigner.assign(789, spec)


def test_project_field_mapping_with_none_values(monkeypatch: MonkeyPatch) -> None:
    """Test project field mapping when spec has None values."""
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    config = ProjectConfig(
        enabled=True,
        number=123,
        field_mappings={"milestone": "Priority", "status": "Status"},
    )
    assigner = GitHubProjectAssigner(config)

    spec = MockIssueSpec(milestone=None, status=None)

    # Should not raise errors even with None values
    assigner.assign(789, spec)


@patch("subprocess.run")
def test_github_project_assigner_get_issue_id_real_mode(
    mock_run: MagicMock, monkeypatch: MonkeyPatch
) -> None:
    """Test getting issue ID in real mode (not mock)."""
    # Ensure mock mode is disabled for this test
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "0")
    # Setup mock subprocess result
    mock_result = MagicMock()
    mock_result.stdout = "MDU6SXNzdWUxMjM0NTY3ODk=\n"
    mock_run.return_value = mock_result

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    issue_id = assigner._get_issue_id(456)

    assert issue_id == "MDU6SXNzdWUxMjM0NTY3ODk="
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert any("gh" in str(arg) for arg in args)
    assert "api" in args
    assert "repos/:owner/:repo/issues/456" in args


@patch("subprocess.run")
def test_github_project_assigner_get_issue_id_error(
    mock_run: MagicMock, monkeypatch: MonkeyPatch
) -> None:
    """Test getting issue ID when GitHub CLI fails."""
    # Ensure mock mode is disabled for this test to exercise the real path
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "0")
    mock_run.side_effect = subprocess.CalledProcessError(1, "gh")

    config = ProjectConfig(enabled=True, number=123, field_mappings={})
    assigner = GitHubProjectAssigner(config)

    issue_id = assigner._get_issue_id(456)

    assert issue_id is None
    mock_run.assert_called_once()
