"""Tests for issuesuite doctor environment parity checks (ADR-0004)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from issuesuite.cli import _doctor_git_hooks_check, _doctor_lockfile_check, _doctor_tool_version_check


def test_doctor_tool_version_check_all_present(capsys):
    """Verify tool version check passes when all tools are available."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        # Mock successful tool version checks
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"tool 1.0.0\n"
        )
        
        _doctor_tool_version_check(warnings)
    
    # Should have checked all 4 tools
    assert mock_run.call_count == 4
    # No warnings when all tools are present
    assert len(warnings) == 0
    
    captured = capsys.readouterr()
    assert "[doctor] ruff:" in captured.out
    assert "[doctor] mypy:" in captured.out
    assert "[doctor] pytest:" in captured.out
    assert "[doctor] nox:" in captured.out


def test_doctor_tool_version_check_missing_tools(capsys):
    """Verify tool version check warns when tools are missing."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        # Mock missing tools (FileNotFoundError)
        mock_run.side_effect = FileNotFoundError
        
        _doctor_tool_version_check(warnings)
    
    # Should warn about missing tools
    assert len(warnings) == 1
    assert "Development tools not found" in warnings[0]
    assert "ruff" in warnings[0]
    assert "mypy" in warnings[0]
    assert "pytest" in warnings[0]
    assert "nox" in warnings[0]


def test_doctor_tool_version_check_version_check_failed(capsys):
    """Verify tool version check handles tools that exist but fail version check."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        # Mock tool exists but version check fails
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=b""
        )
        
        _doctor_tool_version_check(warnings)
    
    # Should not warn about missing tools since they exist
    assert len(warnings) == 0
    
    captured = capsys.readouterr()
    assert "available but version check failed" in captured.out


def test_doctor_lockfile_check_synchronized(capsys):
    """Verify lockfile check passes when lockfiles are synchronized."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path("/fake/project")
                _doctor_lockfile_check(warnings)
    
    # No warnings when lockfiles are synchronized
    assert len(warnings) == 0
    
    captured = capsys.readouterr()
    assert "lockfiles: synchronized" in captured.out


def test_doctor_lockfile_check_out_of_sync(capsys):
    """Verify lockfile check warns when lockfiles are out of sync."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path("/fake/project")
                _doctor_lockfile_check(warnings)
    
    # Should warn about out-of-sync lockfiles
    assert len(warnings) == 1
    assert "Lockfiles out of sync" in warnings[0]
    assert "./scripts/refresh-deps.sh" in warnings[0]


def test_doctor_lockfile_check_script_not_found(capsys):
    """Verify lockfile check skips gracefully when script not found."""
    warnings: list[str] = []
    
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/project")
            _doctor_lockfile_check(warnings)
    
    # No warnings when script doesn't exist
    assert len(warnings) == 0
    
    captured = capsys.readouterr()
    assert "refresh-deps.sh not found" in captured.out


def test_doctor_git_hooks_check_configured(capsys):
    """Verify git hooks check passes when hooks are configured."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"/path/to/project/.githooks\n"
        )
        
        _doctor_git_hooks_check(warnings)
    
    # No warnings when hooks are configured
    assert len(warnings) == 0
    
    captured = capsys.readouterr()
    assert "git hooks:" in captured.out
    assert ".githooks" in captured.out


def test_doctor_git_hooks_check_not_configured(capsys):
    """Verify git hooks check warns when hooks are not configured."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        
        _doctor_git_hooks_check(warnings)
    
    # Should warn about missing hooks
    assert len(warnings) == 1
    assert "Git hooks not configured" in warnings[0]
    assert "./scripts/setup-dev-env.sh" in warnings[0]


def test_doctor_git_hooks_check_wrong_path(capsys):
    """Verify git hooks check warns when hooks path is incorrect."""
    warnings: list[str] = []
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"/some/other/path\n"
        )
        
        _doctor_git_hooks_check(warnings)
    
    # Should warn about incorrect path
    assert len(warnings) == 1
    assert "Git hooks not configured correctly" in warnings[0]


def test_doctor_command_includes_parity_checks(tmp_path):
    """Integration test: verify doctor command runs all parity checks."""
    config = tmp_path / "issue_suite.config.yaml"
    config.write_text("version: 1\nsource:\n  file: ISSUES.md\n")
    
    # Run doctor command
    result = subprocess.run(
        ["python", "-m", "issuesuite", "doctor", "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    # Doctor should run but may report problems
    assert result.returncode in (0, 2)  # 0=ok, 2=problems
    
    # Verify parity checks are included in output
    output = result.stdout + result.stderr
    assert "[doctor] checking environment parity" in output or "[doctor] ruff:" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
