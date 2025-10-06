from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def quality_gate_script():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "quality_gates.py"
    spec = importlib.util.spec_from_file_location("quality_gates_script", script_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.skip("Unable to load quality_gates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_default_gates_include_dependency_scan(quality_gate_script):
    gates = quality_gate_script.build_default_gates()
    names = [gate.name for gate in gates]
    assert "Dependencies" in names
    dependencies_gate = next(g for g in gates if g.name == "Dependencies")
    assert dependencies_gate.command == [
        quality_gate_script.sys.executable,
        "-m",
        "issuesuite.dependency_audit",
    ]


def test_secrets_gate_uses_repo_baseline(quality_gate_script):
    gates = quality_gate_script.build_default_gates()
    secrets_gate = next(g for g in gates if g.name == "Secrets")
    assert "--baseline" in secrets_gate.command
    baseline_index = secrets_gate.command.index("--baseline")
    baseline_arg = secrets_gate.command[baseline_index + 1]
    expected_path = quality_gate_script.SECRETS_BASELINE
    assert Path(baseline_arg) == expected_path
    repo_root = Path(__file__).resolve().parents[1]
    assert expected_path == repo_root / ".secrets.baseline"


def test_performance_report_gate_generates_artifact(quality_gate_script):
    gates = quality_gate_script.build_default_gates()
    report_gate = next(g for g in gates if g.name == "Performance Report")
    assert report_gate.command[0] == quality_gate_script.sys.executable
    script_path = Path(report_gate.command[1])
    assert script_path.name == "generate_performance_report.py"
    assert script_path.exists()


def test_performance_budget_gate_runs_check(quality_gate_script):
    gates = quality_gate_script.build_default_gates()
    budget_gate = next(g for g in gates if g.name == "Performance Budget")
    assert budget_gate.command[:3] == [
        quality_gate_script.sys.executable,
        "-m",
        "issuesuite.benchmarking",
    ]
    assert "--check" in budget_gate.command
