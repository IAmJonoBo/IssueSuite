from __future__ import annotations

import argparse
import sys
from pathlib import Path

from issuesuite.next_steps_validator import DEFAULT_FILES, validate_next_steps


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate repository Next Steps trackers against governance expectations.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional explicit Next Steps file paths to validate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else None)
    targets = args.paths or [path for path in DEFAULT_FILES if path.exists()]
    try:
        validate_next_steps(targets if targets else None)
    except ValueError as exc:  # pragma: no cover - exercised via integration tests
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
