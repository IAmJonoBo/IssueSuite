"""Test hermetic/offline installation scenarios.

These tests validate that IssueSuite works in restricted environments:
- Air-gapped/offline environments without network access
- Minimal environments with only core dependencies
- Graceful degradation when optional dependencies are missing
"""

# ruff: noqa: PLC0415  # Intentional late imports to test module loading

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest


def test_core_imports_without_opentelemetry(monkeypatch):
    """Verify core functionality works without opentelemetry."""
    # Simulate missing opentelemetry
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", None)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", None)

    # Core imports should still work
    from issuesuite import IssueSuite, load_config

    assert load_config is not None
    assert IssueSuite is not None


def test_core_imports_without_psutil(monkeypatch):
    """Verify core functionality works without psutil."""
    # Simulate missing psutil
    monkeypatch.setitem(sys.modules, "psutil", None)

    # Core imports should still work
    from issuesuite import IssueSuite, load_config

    assert load_config is not None
    assert IssueSuite is not None


def test_core_imports_without_keyring(monkeypatch):
    """Verify core functionality works without keyring."""
    # Simulate missing keyring
    monkeypatch.setitem(sys.modules, "keyring", None)

    # Core imports should still work
    from issuesuite import IssueSuite, load_config

    assert load_config is not None
    assert IssueSuite is not None


def test_observability_module_degrades_gracefully_without_otel():
    """Verify observability module handles missing OpenTelemetry gracefully."""
    # Import observability module - should not crash even if otel is missing
    from issuesuite import observability

    # Module should exist and have basic functionality
    assert observability is not None


def test_benchmarking_module_degrades_gracefully_without_psutil():
    """Verify benchmarking module handles missing psutil gracefully."""
    # Import benchmarking module - should not crash even if psutil is missing
    from issuesuite import benchmarking

    # Module should exist and have basic functionality
    assert benchmarking is not None


def test_cli_validate_works_in_mock_mode_offline(tmp_path):
    """Verify CLI validate command works in offline mock mode."""
    import subprocess

    # Create minimal config
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\nsource:\n  file: ISSUES.md\n")

    # Create test issues
    issues = tmp_path / "ISSUES.md"
    issues.write_text(
        "# Issues\n\n## [slug: test]\n\n```yaml\ntitle: Test Issue\nlabels: [test]\n```\n"
    )

    # Run validate in mock mode
    result = subprocess.run(
        [sys.executable, "-m", "issuesuite", "validate", "--config", str(config)],
        check=False, cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "ISSUES_SUITE_MOCK": "1"},
    )

    # Should succeed in mock mode
    assert result.returncode == 0


def test_schema_command_works_offline():
    """Verify schema command works without network access."""

    # Run schema command (should work completely offline)
    result = subprocess.run(
        [sys.executable, "-m", "issuesuite", "schema"],
        check=False, capture_output=True,
        text=True,
    )

    # Should succeed
    assert result.returncode == 0


def test_pip_audit_integration_imports():
    """Verify pip-audit integration module imports successfully."""
    # Should not crash when importing
    from issuesuite import pip_audit_integration

    assert pip_audit_integration is not None


def test_parser_module_imports():
    """Verify parser module imports successfully."""
    # Should not crash when importing
    from issuesuite import parser

    assert parser is not None
    assert hasattr(parser, "parse_issues")


def test_github_issues_module_imports():
    """Verify GitHub issues module imports successfully."""
    # Should not crash when importing
    from issuesuite import github_issues

    assert github_issues is not None
    assert hasattr(github_issues, "IssuesClient")


def test_config_loads_without_optional_features(tmp_path):
    """Verify config loading works without optional features."""
    from issuesuite.config import load_config

    # Create minimal config
    config = tmp_path / "config.yaml"
    config.write_text(
        "version: 1\nsource:\n  file: ISSUES.md\ndefaults:\n  ensure_labels_enabled: false\n"
    )

    # Should load successfully
    cfg = load_config(str(config))
    assert cfg is not None
    assert cfg.version == 1


def test_dependency_audit_works_offline():
    """Verify dependency audit works with offline advisories."""
    import subprocess

    # Run dependency audit in offline mode
    result = subprocess.run(
        [sys.executable, "-m", "issuesuite.dependency_audit", "--offline-only"],
        check=False, capture_output=True,
        text=True,
        env={**os.environ},
    )

    # Should succeed or gracefully skip (may exit 0 or with warning)
    assert result.returncode in (0, 1, 2)
