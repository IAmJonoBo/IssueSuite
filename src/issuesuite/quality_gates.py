"""Utility helpers for enforcing repository quality gates."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from subprocess import (  # nosec B404 - subprocess required for tooling commands
    CompletedProcess,
    run,
)
from xml.etree import (  # nosec B405 - coverage reports are produced locally by pytest
    ElementTree,
)


@dataclass(frozen=True)
class Gate:
    """Definition of a single quality gate command."""

    name: str
    command: Sequence[str]
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    coverage_threshold: float | None = None
    coverage_report: Path = Path("coverage.xml")


@dataclass
class GateResult:
    """Outcome of running a gate."""

    gate: Gate
    returncode: int
    stdout: str
    stderr: str
    coverage: float | None
    success: bool


class QualityGateError(RuntimeError):
    """Raised when a gate fails (command failure or metric shortfall)."""

    def __init__(self, result: GateResult, prior_results: Iterable[GateResult]):
        self.result = result
        self.prior_results = list(prior_results)
        super().__init__(f"Gate '{result.gate.name}' failed")


def _run_command(gate: Gate) -> CompletedProcess[str]:
    return run(  # nosec B603 - commands are predefined in Gate definitions
        gate.command,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(gate.cwd) if gate.cwd else None,
        env=dict(gate.env) if gate.env else None,
    )


def _load_coverage_percentage(report_path: Path) -> float:
    tree = ElementTree.parse(report_path)  # nosec B314 - report is generated locally by coverage.py
    root = tree.getroot()
    rate = root.attrib.get("line-rate")
    if rate is None:
        raise ValueError("coverage.xml missing line-rate attribute")
    return float(rate) * 100.0


def run_gates(
    gates: Sequence[Gate],
    *,
    command_runner: Callable[[Gate], CompletedProcess[str]] = _run_command,
    coverage_loader: Callable[[Path], float] = _load_coverage_percentage,
) -> list[GateResult]:
    results: list[GateResult] = []
    for gate in gates:
        completed = command_runner(gate)
        result = GateResult(
            gate=gate,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            coverage=None,
            success=completed.returncode == 0,
        )
        results.append(result)
        if not result.success:
            raise QualityGateError(result, results[:-1])
        if gate.coverage_threshold is not None:
            coverage = coverage_loader(gate.coverage_report)
            result.coverage = coverage
            result.success = coverage >= gate.coverage_threshold
            if not result.success:
                raise QualityGateError(result, results[:-1])
    return results


def format_summary(results: Sequence[GateResult]) -> str:
    lines: list[str] = []
    for result in results:
        status = "PASS" if result.success else "FAIL"
        coverage_note = (
            f" (coverage {result.coverage:.2f}% >= {result.gate.coverage_threshold:.2f}%)"
            if result.coverage is not None and result.gate.coverage_threshold is not None
            else ""
        )
        lines.append(f"[{status}] {result.gate.name}{coverage_note}")
    return "\n".join(lines)


__all__ = ["Gate", "GateResult", "QualityGateError", "run_gates", "format_summary"]
