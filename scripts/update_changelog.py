"""Utility script to safely append entries to ``CHANGELOG.md``.

The script obtains a non-blocking file lock before mutating the changelog so
that CI or parallel developer workflows fail fast instead of hanging waiting
for another process to release the file.  When the lock cannot be acquired the
script raises ``RuntimeError`` to encourage the caller to retry manually.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

HEADER = "# Changelog"


def _acquire_lock(handle: TextIO) -> None:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:  # pragma: no cover - exercised in tests via monkeypatch
        raise RuntimeError("CHANGELOG.md is locked by another process") from exc


def _render_entry(version: str, highlights: Iterable[str]) -> str:
    date = _dt.date.today().isoformat()
    lines = [f"## {version} - {date}", ""]
    for highlight in highlights:
        lines.append(f"- {highlight.strip()}")
    lines.append("")
    return "\n".join(lines)


def update_changelog(path: Path, *, version: str, highlights: Iterable[str]) -> str:
    content = path.read_text(encoding="utf-8")
    if HEADER not in content:
        raise RuntimeError("CHANGELOG.md missing top-level header")
    entry = _render_entry(version, highlights)
    updated = content.replace(HEADER, f"{HEADER}\n\n{entry}", 1)
    with path.open("r+", encoding="utf-8") as handle:
        _acquire_lock(handle)
        handle.seek(0)
        handle.write(updated)
        handle.truncate()
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a release entry to CHANGELOG.md")
    parser.add_argument("version", help="Version identifier, e.g., 0.1.12")
    parser.add_argument(
        "--highlight",
        action="append",
        required=True,
        help="Bullet point describing a notable change; may be provided multiple times.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to the changelog file (default: CHANGELOG.md)",
    )
    args = parser.parse_args(argv)

    entry = update_changelog(args.changelog, version=args.version, highlights=args.highlight)
    print(entry)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
