"""Tests for UX helpers module."""

from __future__ import annotations

import io
import os
from typing import Any

import pytest

from issuesuite.ux import (
    Colors,
    colorize,
    print_error,
    print_header,
    print_info,
    print_operation_status,
    print_success,
    print_summary_box,
    print_warning,
)


def test_colorize_with_tty_support(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test colorize adds colors when TTY is supported."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    stream = io.StringIO()
    # Make it look like a TTY
    stream.isatty = lambda: True  # type: ignore[method-assign]

    result = colorize("test", Colors.RED, bold=True, stream=stream)
    assert Colors.RED in result
    assert Colors.BOLD in result
    assert Colors.RESET in result
    assert "test" in result


def test_colorize_respects_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test colorize respects NO_COLOR environment variable."""
    monkeypatch.setenv("NO_COLOR", "1")

    result = colorize("test", Colors.RED, bold=True)
    assert result == "test"
    assert Colors.RED not in result
    assert Colors.RESET not in result


def test_colorize_no_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test colorize returns plain text when not a TTY."""
    monkeypatch.delenv("NO_COLOR", raising=False)

    stream = io.StringIO()
    # Default StringIO is not a TTY

    result = colorize("test", Colors.GREEN, stream=stream)
    assert result == "test"
    assert Colors.GREEN not in result


def test_print_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_success outputs message."""
    monkeypatch.setenv("NO_COLOR", "1")  # Disable colors for predictable output

    print_success("Operation completed")
    captured = capsys.readouterr()
    assert "Operation completed" in captured.out
    assert "✓" in captured.out


def test_print_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_error outputs to stderr."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_error("Something went wrong")
    captured = capsys.readouterr()
    assert "Something went wrong" in captured.err
    assert "✗" in captured.err


def test_print_warning(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_warning outputs message."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_warning("Be careful")
    captured = capsys.readouterr()
    assert "Be careful" in captured.out
    assert "⚠" in captured.out


def test_print_info(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_info outputs message."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_info("For your information")
    captured = capsys.readouterr()
    assert "For your information" in captured.out
    assert "ℹ" in captured.out


def test_print_header(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_header outputs bold message."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_header("Section Title")
    captured = capsys.readouterr()
    assert "Section Title" in captured.out


def test_print_summary_box(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test print_summary_box formats key-value pairs."""
    monkeypatch.setenv("NO_COLOR", "1")

    items = [
        ("Key 1", "value1"),
        ("Key 2", 42),
        ("Key 3", 0),
    ]

    print_summary_box("Test Summary", items)
    captured = capsys.readouterr()

    assert "Test Summary" in captured.out
    assert "Key 1" in captured.out
    assert "value1" in captured.out
    assert "Key 2" in captured.out
    assert "42" in captured.out
    assert "Key 3" in captured.out
    assert "─" in captured.out  # Box border


def test_print_operation_status_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test print_operation_status with success status."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_operation_status("sync", "success", "all good")
    captured = capsys.readouterr()

    assert "sync" in captured.out
    assert "success" in captured.out
    assert "all good" in captured.out
    assert "✓" in captured.out


def test_print_operation_status_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test print_operation_status with failed status."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_operation_status("sync", "failed", "error occurred")
    captured = capsys.readouterr()

    assert "sync" in captured.out
    assert "failed" in captured.out
    assert "error occurred" in captured.out
    assert "✗" in captured.out


def test_print_operation_status_skipped(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test print_operation_status with skipped status."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_operation_status("sync", "skipped")
    captured = capsys.readouterr()

    assert "sync" in captured.out
    assert "skipped" in captured.out
    assert "○" in captured.out


def test_print_summary_box_empty_items(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test print_summary_box with empty items list."""
    monkeypatch.setenv("NO_COLOR", "1")

    print_summary_box("Empty Summary", [])
    captured = capsys.readouterr()

    assert "Empty Summary" in captured.out
    assert "─" in captured.out


def test_colorize_dumb_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test colorize disables colors on dumb terminal."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dumb")

    stream = io.StringIO()
    stream.isatty = lambda: True  # type: ignore[method-assign]

    result = colorize("test", Colors.BLUE, stream=stream)
    assert result == "test"
    assert Colors.BLUE not in result
