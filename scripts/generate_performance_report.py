"""Generate a deterministic performance_report.json for CI quality gates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from issuesuite.performance_report import generate_ci_reference_report  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "performance_report.json",
        help="Path where the performance report should be written",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output = args.output
    if not output.is_absolute():
        output = Path.cwd() / output

    try:
        path = generate_ci_reference_report(output)
    except Exception as exc:  # pragma: no cover - surfaced in CI logs
        print(f"Failed to generate performance report: {exc}", file=sys.stderr)
        return 1

    print(f"Performance report generated at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
