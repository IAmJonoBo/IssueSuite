"""Run the IssueSuite quality gate suite."""
from __future__ import annotations

# ruff: noqa: I001 - sys.path manipulation is required before importing project modules

import json
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from issuesuite.quality_gates import (  # noqa: E402
    Gate,
    GateResult,
    QualityGateError,
    format_summary,
    run_gates,
)


SECRETS_BASELINE = PROJECT_ROOT / ".secrets.baseline"


def build_default_gates() -> list[Gate]:
    return [
        Gate(
            name="Tests",
            command=[
                "pytest",
                "--cov=issuesuite",
                "--cov-report=term",
                "--cov-report=xml",
            ],
            coverage_threshold=65.0,
            coverage_report=PROJECT_ROOT / "coverage.xml",
        ),
        Gate(name="Lint", command=["ruff", "check"]),
        Gate(name="Type Check", command=["mypy", "src"]),
        Gate(name="Security", command=["bandit", "-r", "src"]),
        Gate(
            name="Dependencies",
            command=[
                sys.executable,
                "-m",
                "issuesuite.dependency_audit",
            ],
        ),
        Gate(
            name="pip-audit",
            command=[
                "pip-audit",
                "--progress-spinner",
                "off",
                "--strict",
            ],
        ),
        Gate(
            name="Secrets",
            command=[
                "detect-secrets",
                "scan",
                "--baseline",
                str(SECRETS_BASELINE),
            ],
        ),
        Gate(
            name="Performance Report",
            command=[
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_performance_report.py"),
            ],
        ),
        Gate(
            name="Performance Budget",
            command=[
                sys.executable,
                "-m",
                "issuesuite.benchmarking",
                "--check",
                "--report",
                str(PROJECT_ROOT / "performance_report.json"),
            ],
        ),
        Gate(
            name="Offline Advisories Freshness",
            command=[
                sys.executable,
                "-m",
                "issuesuite.advisory_refresh",
                "--check",
                "--max-age-days",
                "30",
            ],
        ),
        Gate(name="Build", command=["python", "-m", "build"]),
    ]


def main() -> int:
    try:
        results = run_gates(build_default_gates())
    except QualityGateError as exc:
        results = [*exc.prior_results, exc.result]
        print(format_summary(results), file=sys.stderr)
        _write_report(results)
        return 1

    print(format_summary(results))
    _write_report(results)
    return 0


def _write_report(results: Sequence[GateResult]) -> None:
    report = []
    for result in results:
        report.append(
            {
                "name": result.gate.name,
                "command": list(result.gate.command),
                "success": result.success,
                "returncode": result.returncode,
                "coverage": result.coverage,
            }
        )
    out_path = PROJECT_ROOT / "quality_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
