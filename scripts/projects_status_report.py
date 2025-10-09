"""Generate a GitHub Projects status report from IssueSuite telemetry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from issuesuite.projects_status import generate_report, render_comment, serialize_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--next-steps",
        dest="next_steps",
        action="append",
        type=Path,
        help="Path to a Next Steps tracker (defaults to repository root files)",
    )
    parser.add_argument(
        "--coverage",
        dest="coverage",
        type=Path,
        help="Path to coverage_projects_payload.json (defaults to repository export)",
    )
    parser.add_argument(
        "--output",
        dest="output",
        type=Path,
        default=Path("projects_status_report.json"),
        help="Where to write the JSON report",
    )
    parser.add_argument(
        "--comment-output",
        dest="comment_output",
        type=Path,
        help="Optional path for a rendered Markdown comment",
    )
    parser.add_argument(
        "--lookahead-days",
        dest="lookahead_days",
        type=int,
        default=None,
        help="Override the due-soon lookahead window (defaults to 7 days)",
    )
    parser.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Suppress console output (still writes artifacts)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = generate_report(
        next_steps_paths=args.next_steps,
        coverage_payload_path=args.coverage,
        lookahead_days=args.lookahead_days,
    )

    serialized = serialize_report(report)
    args.output.write_text(json.dumps(serialized, indent=2) + "\n", encoding="utf-8")

    comment = render_comment(report) + "\n"
    if args.comment_output:
        args.comment_output.write_text(comment, encoding="utf-8")
    if not args.quiet:
        print(comment, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
