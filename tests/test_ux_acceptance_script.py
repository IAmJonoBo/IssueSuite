from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from subprocess import CompletedProcess
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def ux_acceptance_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ux_acceptance.py"
    spec = importlib.util.spec_from_file_location("ux_acceptance", script_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.skip("unable to load ux_acceptance.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


class DummyProcess(CompletedProcess[str]):
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        super().__init__(args=["issuesuite"], returncode=returncode, stdout=stdout, stderr="")


def test_run_checks_passes(tmp_path: Path, ux_acceptance_module: ModuleType) -> None:
    help_text = "Usage: issuesuite\n\nOptions:\n  --help  Show this message.\n"
    process = DummyProcess(stdout=help_text)
    report = ux_acceptance_module.run_checks(
        commands=[()],
        runner=lambda _: process,
        output_path=tmp_path / "ux.json",
    )
    assert report["passed"] is True
    payload = json.loads((tmp_path / "ux.json").read_text(encoding="utf-8"))
    assert payload["checks"][0]["status"] == "pass"


def test_run_checks_detects_failures(tmp_path: Path, ux_acceptance_module: ModuleType) -> None:
    long_line = "Usage: issuesuite " + "x" * 150
    process = DummyProcess(stdout=long_line)
    report = ux_acceptance_module.run_checks(
        commands=[()],
        runner=lambda _: process,
        output_path=tmp_path / "ux.json",
    )
    assert report["passed"] is False
    assert report["failures"][0]["status"] == "fail"
