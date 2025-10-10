"""Run the IssueSuite quality gate suite."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

# ruff: noqa: I001 - sys.path manipulation is required before importing project modules


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from issuesuite.coverage_trends import (  # noqa: E402
    CoverageTrendError as CoverageTrendRuntimeError,
)
from issuesuite.coverage_trends import (  # noqa: E402
    export_trends,
)
from issuesuite.quality_gates import (  # noqa: E402
    Gate,
    GateResult,
    QualityGateError,
    format_summary,
    run_gates,
)

SECRETS_BASELINE = PROJECT_ROOT / ".secrets.baseline"
COVERAGE_REPORT = PROJECT_ROOT / "coverage.xml"
COVERAGE_SUMMARY = PROJECT_ROOT / "coverage_summary.json"
COVERAGE_HISTORY = PROJECT_ROOT / "coverage_trends.json"
COVERAGE_SNAPSHOT = PROJECT_ROOT / "coverage_trends_latest.json"
COVERAGE_PROJECT_PAYLOAD = PROJECT_ROOT / "coverage_projects_payload.json"

CRITICAL_MODULE_THRESHOLDS: dict[str, float] = {
    "issuesuite/cli.py": 90.0,
    "issuesuite/core.py": 90.0,
    "issuesuite/github_issues.py": 90.0,
    "issuesuite/project.py": 90.0,
    "issuesuite/pip_audit_integration.py": 90.0,
}


@dataclass
class ModuleCoverageError(RuntimeError):
    coverages: dict[str, float]
    deficits: dict[str, float]
    missing: list[str]

    def __post_init__(self) -> None:  # pragma: no cover - dataclass hook
        messages: list[str] = []
        if self.deficits:
            deficit_lines = ", ".join(
                f"{module}={coverage:.2f}% (< {CRITICAL_MODULE_THRESHOLDS[module]:.2f}%)"
                for module, coverage in sorted(self.deficits.items())
            )
            messages.append(f"Coverage shortfall: {deficit_lines}")
        if self.missing:
            missing_list = ", ".join(sorted(self.missing))
            messages.append(f"Missing modules: {missing_list}")
        if not messages:
            messages.append("Unknown module coverage failure")
        super().__init__("; ".join(messages))


class CoverageTrendExportError(RuntimeError):
    """Raised when coverage trends cannot be exported."""


def build_default_gates() -> list[Gate]:
    python = sys.executable
    return [
        Gate(
            name="Tests",
            command=[
                "pytest",
                "--cov=issuesuite",
                "--cov-report=term",
                "--cov-report=xml",
            ],
            coverage_threshold=85.0,
            coverage_report=PROJECT_ROOT / "coverage.xml",
        ),
        Gate(name="Format", command=["ruff", "format", "--check"]),
        Gate(name="Lint", command=["ruff", "check"]),
        Gate(name="Type Check", command=["mypy", "src"]),
        Gate(
            name="Type Telemetry",
            command=[
                python,
                str(PROJECT_ROOT / "scripts" / "type_coverage_report.py"),
            ],
        ),
        Gate(name="Security", command=[python, "-m", "bandit", "-r", "src"]),
        Gate(
            name="Dependencies",
            command=[
                python,
                "-m",
                "issuesuite.dependency_audit",
            ],
        ),
        Gate(
            name="pip-audit",
            command=[
                python,
                "-m",
                "issuesuite.cli",
                "security",
                "--pip-audit",
                "--pip-audit-disable-online",
                "--pip-audit-arg=--progress-spinner",
                "--pip-audit-arg",
                "off",
                "--pip-audit-arg=--strict",
            ],
        ),
        Gate(
            name="Secrets",
            command=[
                python,
                "-m",
                "detect_secrets",
                "scan",
                "--baseline",
                str(SECRETS_BASELINE),
            ],
        ),
        Gate(name="Bytecode Compile", command=[python, "-m", "compileall", "src"]),
        Gate(
            name="Performance Report",
            command=[
                python,
                str(PROJECT_ROOT / "scripts" / "generate_performance_report.py"),
            ],
        ),
        Gate(
            name="Performance Budget",
            command=[
                python,
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
                python,
                "-m",
                "issuesuite.advisory_refresh",
                "--check",
                "--max-age-days",
                "30",
            ],
        ),
        Gate(name="Build", command=[python, "-m", "build"]),
        Gate(
            name="Next Steps Governance",
            command=[python, str(PROJECT_ROOT / "scripts" / "verify_next_steps.py")],
        ),
        Gate(
            name="UX Acceptance",
            command=[python, str(PROJECT_ROOT / "scripts" / "ux_acceptance.py")],
        ),
    ]


def main() -> int:
    module_coverages: dict[str, float] | None = None
    try:
        results = run_gates(build_default_gates())
        module_coverages = _enforce_module_thresholds(COVERAGE_REPORT, CRITICAL_MODULE_THRESHOLDS)
    except ModuleCoverageError as exc:
        module_coverages = exc.coverages
        print(format_summary(results), file=sys.stderr)
        print(str(exc), file=sys.stderr)
        _write_report(results)
        try:
            _persist_coverage_artifacts(module_coverages)
        except CoverageTrendExportError as trend_exc:
            print(str(trend_exc), file=sys.stderr)
        return 1
    except QualityGateError as exc:
        results = [*exc.prior_results, exc.result]
        print(format_summary(results), file=sys.stderr)
        _write_report(results)
        if module_coverages is not None:
            try:
                _persist_coverage_artifacts(module_coverages)
            except CoverageTrendExportError as trend_exc:
                print(str(trend_exc), file=sys.stderr)
        return 1

    print(format_summary(results))
    _write_report(results)
    try:
        if module_coverages is None:
            module_coverages = _load_module_coverages(COVERAGE_REPORT)
    except ModuleCoverageError as exc:
        module_coverages = exc.coverages
        print(str(exc), file=sys.stderr)
        try:
            _persist_coverage_artifacts(module_coverages)
        except CoverageTrendExportError as trend_exc:
            print(str(trend_exc), file=sys.stderr)
        return 1
    try:
        _persist_coverage_artifacts(module_coverages)
    except CoverageTrendExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
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


def _write_module_summary(
    coverages: Mapping[str, float],
    *,
    summary_path: Path = COVERAGE_SUMMARY,
) -> None:
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    modules: list[dict[str, Any]] = []
    for module, threshold in sorted(CRITICAL_MODULE_THRESHOLDS.items()):
        coverage = coverages.get(module)
        normalized_coverage = coverage / 100.0 if coverage is not None else None
        normalized_threshold = threshold / 100.0
        modules.append(
            {
                "module": module,
                "coverage": normalized_coverage,
                "threshold": normalized_threshold,
                "meets_threshold": coverage is not None and coverage >= threshold,
            }
        )
    payload = {
        "generated_at": timestamp,
        "report": str(COVERAGE_REPORT),
        "modules": modules,
    }
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _enforce_module_thresholds(
    report_path: Path, thresholds: Mapping[str, float]
) -> dict[str, float]:
    coverages = _load_module_coverages(report_path)
    deficits: dict[str, float] = {}
    missing: list[str] = []
    for module, threshold in thresholds.items():
        coverage = coverages.get(module)
        if coverage is None:
            missing.append(module)
            continue
        if coverage < threshold:
            deficits[module] = coverage
    if deficits or missing:
        raise ModuleCoverageError(coverages, deficits, missing)
    return coverages


def _load_module_coverages(report_path: Path) -> dict[str, float]:
    if not report_path.exists():
        raise ModuleCoverageError({}, {}, sorted(CRITICAL_MODULE_THRESHOLDS))
    tree = ElementTree.parse(report_path)
    coverages: dict[str, float] = {}
    for class_node in tree.findall(".//class"):
        filename = class_node.attrib.get("filename")
        rate = class_node.attrib.get("line-rate")
        if not filename or rate is None:
            continue
        module_key = _normalize_module_path(filename)
        if module_key:
            coverages[module_key] = float(rate) * 100.0
    return coverages


def _normalize_module_path(filename: str) -> str:
    path = Path(filename)
    parts = list(path.parts)
    try:
        start = parts.index("issuesuite")
        relevant = parts[start:]
    except ValueError:
        relevant = parts[-2:]
    normalized = "/".join(relevant)
    return normalized


def _persist_coverage_artifacts(
    coverages: Mapping[str, float],
    *,
    summary_path: Path = COVERAGE_SUMMARY,
    history_path: Path = COVERAGE_HISTORY,
    snapshot_path: Path = COVERAGE_SNAPSHOT,
    project_payload_path: Path = COVERAGE_PROJECT_PAYLOAD,
    now: datetime | None = None,
) -> None:
    _write_module_summary(coverages, summary_path=summary_path)
    _export_coverage_trends(
        summary_path=summary_path,
        history_path=history_path,
        snapshot_path=snapshot_path,
        project_payload_path=project_payload_path,
        now=now,
    )


def _export_coverage_trends(
    *,
    summary_path: Path = COVERAGE_SUMMARY,
    history_path: Path = COVERAGE_HISTORY,
    snapshot_path: Path = COVERAGE_SNAPSHOT,
    project_payload_path: Path = COVERAGE_PROJECT_PAYLOAD,
    now: datetime | None = None,
) -> None:
    try:
        export_trends(
            summary_path=summary_path,
            history_path=history_path,
            snapshot_path=snapshot_path,
            project_payload_path=project_payload_path,
            now=now,
        )
    except CoverageTrendRuntimeError as exc:  # pragma: no cover - defensive
        raise CoverageTrendExportError(str(exc)) from exc


if __name__ == "__main__":
    sys.exit(main())
