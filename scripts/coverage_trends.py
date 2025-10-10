"""CLI wrapper to export coverage trend telemetry for GitHub Projects."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from issuesuite.coverage_trends import export_trends


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export coverage trends for dashboards"
    )
    parser.add_argument(
        "--summary-path",
        default=None,
        help="Path to coverage_summary.json (defaults to repository root)",
    )
    parser.add_argument(
        "--history-path",
        default=None,
        help="Path to coverage_trends.json (defaults to repository root)",
    )
    parser.add_argument(
        "--snapshot-path",
        default=None,
        help="Path to coverage_trends_latest.json (defaults to repository root)",
    )
    parser.add_argument(
        "--project-payload-path",
        default=None,
        help="Path to coverage_projects_payload.json (defaults to repository root)",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=200,
        help="Maximum number of history records to retain (default: 200)",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=None,
        help="Override the Frontier target coverage threshold (default: 0.85)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    kwargs = {
        "max_records": args.max_records,
        "now": datetime.now(tz=timezone.utc),
    }
    if args.summary_path:
        kwargs["summary_path"] = Path(args.summary_path)
    if args.history_path:
        kwargs["history_path"] = Path(args.history_path)
    if args.snapshot_path:
        kwargs["snapshot_path"] = Path(args.snapshot_path)
    if args.project_payload_path:
        kwargs["project_payload_path"] = Path(args.project_payload_path)
    if args.target is not None:
        kwargs["target"] = args.target
    export_trends(**kwargs)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
