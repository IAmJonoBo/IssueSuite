from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from subprocess import CompletedProcess
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def type_coverage_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "type_coverage_report.py"
    )
    spec = importlib.util.spec_from_file_location("type_coverage_report", script_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.skip("unable to load type_coverage_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


class DummyProcess(CompletedProcess[str]):
    def __init__(self, stdout: str, stderr: str, returncode: int = 0) -> None:
        super().__init__(
            args=["mypy"], returncode=returncode, stdout=stdout, stderr=stderr
        )


@pytest.fixture()
def dummy_modules(tmp_path: Path) -> Path:
    package = tmp_path / "issuesuite"
    package.mkdir()
    for name in ("alpha.py", "beta.py"):
        (package / name).write_text("x = 1\n", encoding="utf-8")
    return package


def test_generate_report_counts_errors(
    type_coverage_module: ModuleType, tmp_path: Path, dummy_modules: Path
) -> None:
    stdout = str(dummy_modules / "alpha.py") + ":1:1: error: boom\n"
    process = DummyProcess(stdout=stdout, stderr="", returncode=1)

    report = type_coverage_module.generate_report(
        targets=[str(dummy_modules)],
        runner=lambda _: process,
        module_roots=[dummy_modules],
        output_path=tmp_path / "type.json",
    )

    assert report["modules_total"] == 2
    assert report["modules_strict_clean"] == 1
    assert pytest.approx(report["strict_ratio"]) == 0.5
    path = tmp_path / "type.json"
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["modules_total"] == 2


def test_generate_report_handles_no_errors(
    type_coverage_module: ModuleType, tmp_path: Path, dummy_modules: Path
) -> None:
    process = DummyProcess(stdout="", stderr="", returncode=0)
    report = type_coverage_module.generate_report(
        targets=[str(dummy_modules)],
        runner=lambda _: process,
        module_roots=[dummy_modules],
        output_path=tmp_path / "type.json",
    )
    assert report["modules_strict_clean"] == 2
    assert report["modules_total"] == 2
    assert pytest.approx(report["strict_ratio"]) == 1.0
