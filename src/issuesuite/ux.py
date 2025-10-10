"""Simple UX helpers for CLI output - no external dependencies."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright variants
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def _supports_color(stream: TextIO | None = None) -> bool:
    """Check if terminal supports color output."""
    import os  # noqa: PLC0415

    stream = stream or sys.stdout
    # Disable colors if:
    # - NO_COLOR env var is set
    # - not a TTY
    # - TERM is dumb

    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return True


def colorize(text: str, color: str, bold: bool = False, stream: TextIO | None = None) -> str:
    """Apply color to text if terminal supports it."""
    if not _supports_color(stream):
        return text
    prefix = (Colors.BOLD if bold else "") + color
    return f"{prefix}{text}{Colors.RESET}"


def print_success(message: str, stream: TextIO | None = None) -> None:
    """Print success message in green."""
    stream = stream or sys.stdout
    print(
        colorize("✓", Colors.GREEN, bold=True, stream=stream) + " " + message,
        file=stream,
    )


def print_error(message: str, stream: TextIO | None = None) -> None:
    """Print error message in red."""
    stream = stream or sys.stderr
    print(colorize("✗", Colors.RED, bold=True, stream=stream) + " " + message, file=stream)


def print_warning(message: str, stream: TextIO | None = None) -> None:
    """Print warning message in yellow."""
    stream = stream or sys.stdout
    print(
        colorize("⚠", Colors.YELLOW, bold=True, stream=stream) + " " + message,
        file=stream,
    )


def print_info(message: str, stream: TextIO | None = None) -> None:
    """Print info message in blue."""
    stream = stream or sys.stdout
    print(
        colorize("ℹ", Colors.BLUE, bold=True, stream=stream) + " " + message,
        file=stream,
    )


def print_header(message: str, stream: TextIO | None = None) -> None:
    """Print section header in bold cyan."""
    stream = stream or sys.stdout
    print(colorize(message, Colors.CYAN, bold=True, stream=stream), file=stream)


def print_summary_box(
    title: str, items: Sequence[tuple[str, str | int]], stream: TextIO | None = None
) -> None:
    """Print a formatted summary box with key-value pairs."""
    stream = stream or sys.stdout
    max_key_len = max((len(k) for k, _ in items), default=0)

    print(colorize(f"\n{title}", Colors.CYAN, bold=True, stream=stream), file=stream)
    print(colorize("─" * 60, Colors.DIM, stream=stream), file=stream)

    for key, value in items:
        key_formatted = key.ljust(max_key_len)
        value_str = str(value)

        # Color value based on type
        if isinstance(value, int) and value > 0:
            value_colored = colorize(value_str, Colors.GREEN, bold=True, stream=stream)
        elif value_str.lower() in ("true", "yes", "enabled"):
            value_colored = colorize(value_str, Colors.GREEN, stream=stream)
        elif value_str.lower() in ("false", "no", "disabled"):
            value_colored = colorize(value_str, Colors.DIM, stream=stream)
        else:
            value_colored = value_str

        print(f"  {key_formatted}  {value_colored}", file=stream)

    print(colorize("─" * 60, Colors.DIM, stream=stream), file=stream)


def print_operation_status(
    operation: str, status: str, details: str = "", stream: TextIO | None = None
) -> None:
    """Print operation status with appropriate coloring.

    Args:
        operation: Operation name (e.g., "sync", "validate")
        status: Status (e.g., "success", "failed", "skipped")
        details: Optional additional details
        stream: Output stream
    """
    stream = stream or sys.stdout

    status_lower = status.lower()
    if status_lower in ("success", "ok", "passed"):
        icon = colorize("✓", Colors.GREEN, bold=True, stream=stream)
        status_colored = colorize(status, Colors.GREEN, stream=stream)
    elif status_lower in ("failed", "error"):
        icon = colorize("✗", Colors.RED, bold=True, stream=stream)
        status_colored = colorize(status, Colors.RED, bold=True, stream=stream)
    elif status_lower in ("skipped", "unchanged"):
        icon = colorize("○", Colors.YELLOW, stream=stream)
        status_colored = colorize(status, Colors.YELLOW, stream=stream)
    else:
        icon = colorize("•", Colors.BLUE, stream=stream)
        status_colored = status

    operation_colored = colorize(operation, Colors.BOLD, stream=stream)
    message = f"{icon} {operation_colored}: {status_colored}"
    if details:
        message += f" {colorize(f'({details})', Colors.DIM, stream=stream)}"

    print(message, file=stream)
