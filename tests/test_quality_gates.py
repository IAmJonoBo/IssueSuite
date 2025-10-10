from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from issuesuite.quality_gates import Gate, QualityGateError, run_gates


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=["dummy"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_gates_success(tmp_path: Path) -> None:
    report = tmp_path / "coverage.xml"
    report.write_text('<coverage line-rate="0.80" />', encoding="utf-8")

    gate = Gate(
        name="Tests",
        command=["pytest"],
        coverage_threshold=75.0,
        coverage_report=report,
    )

    results = run_gates(
        [gate],
        command_runner=lambda _: _completed(0, stdout="ok"),
    )

    assert results[0].success is True
    assert results[0].coverage == pytest.approx(80.0)


def test_run_gates_command_failure(tmp_path: Path) -> None:
    gate = Gate(name="Lint", command=["ruff", "check"])

    with pytest.raises(QualityGateError) as excinfo:
        run_gates([gate], command_runner=lambda _: _completed(1, stderr="boom"))

    assert excinfo.value.result.gate.name == "Lint"
    assert excinfo.value.result.success is False


def test_run_gates_coverage_failure(tmp_path: Path) -> None:
    report = tmp_path / "coverage.xml"
    report.write_text('<coverage line-rate="0.50" />', encoding="utf-8")

    gate = Gate(
        name="Tests",
        command=["pytest"],
        coverage_threshold=60.0,
        coverage_report=report,
    )

    with pytest.raises(QualityGateError) as excinfo:
        run_gates(
            [gate],
            command_runner=lambda _: _completed(0, stdout="ok"),
        )

    assert excinfo.value.result.gate.name == "Tests"
    assert excinfo.value.result.coverage == pytest.approx(50.0)
