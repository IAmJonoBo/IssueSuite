from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest


@pytest.fixture(scope="module")
def quality_gate_script():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "quality_gates.py"
    spec = importlib.util.spec_from_file_location("quality_gates_script", script_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.skip("Unable to load quality_gates.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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


def test_type_and_ux_gates_present(quality_gate_script):
    gates = quality_gate_script.build_default_gates()
    names = {gate.name for gate in gates}
    assert "Type Telemetry" in names
    assert "UX Acceptance" in names


def test_module_threshold_enforcement_pass(tmp_path, quality_gate_script):
    coverage = tmp_path / "coverage.xml"
    coverage.write_text(
        """
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename="src/issuesuite/core.py" line-rate="0.95" />
                <class filename="src/issuesuite/cli.py" line-rate="0.94" />
              </classes>
            </package>
          </packages>
        </coverage>
        """,
        encoding="utf-8",
    )
    thresholds = {"issuesuite/core.py": 90.0, "issuesuite/cli.py": 90.0}
    coverages = quality_gate_script._enforce_module_thresholds(coverage, thresholds)
    assert coverages["issuesuite/core.py"] == pytest.approx(95.0)
    assert coverages["issuesuite/cli.py"] == pytest.approx(94.0)


def test_module_threshold_enforcement_failure(tmp_path, quality_gate_script):
    coverage = tmp_path / "coverage.xml"
    coverage.write_text(
        """
        <coverage>
          <packages>
            <package>
              <classes>
                <class filename="src/issuesuite/core.py" line-rate="0.80" />
              </classes>
            </package>
          </packages>
        </coverage>
        """,
        encoding="utf-8",
    )
    thresholds = {"issuesuite/core.py": 90.0}
    with pytest.raises(quality_gate_script.ModuleCoverageError) as excinfo:
        quality_gate_script._enforce_module_thresholds(coverage, thresholds)
    assert "Coverage shortfall" in str(excinfo.value)


def test_persist_coverage_artifacts_exports_trends(tmp_path, quality_gate_script):
    summary_path = tmp_path / "coverage_summary.json"
    history_path = tmp_path / "coverage_trends.json"
    snapshot_path = tmp_path / "coverage_trends_latest.json"
    project_payload_path = tmp_path / "coverage_projects_payload.json"
    coverages = {
        "issuesuite/cli.py": 95.0,
        "issuesuite/core.py": 94.0,
        "issuesuite/github_issues.py": 92.0,
        "issuesuite/project.py": 93.0,
        "issuesuite/pip_audit_integration.py": 91.0,
    }

    quality_gate_script._persist_coverage_artifacts(
        coverages,
        summary_path=summary_path,
        history_path=history_path,
        snapshot_path=snapshot_path,
        project_payload_path=project_payload_path,
        now=datetime(2025, 10, 9, 7, 30, tzinfo=timezone.utc),
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "generated_at" in summary
    modules = {module["module"]: module for module in summary["modules"]}
    cli_entry = modules["issuesuite/cli.py"]
    assert cli_entry["coverage"] == pytest.approx(0.95)
    assert cli_entry["threshold"] == pytest.approx(0.7)
    assert cli_entry["meets_threshold"] is True

    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(history) == 1
    entry = history[0]
    assert entry["recorded_at"] == "2025-10-09T07:30:00+00:00"
    assert entry["overall"]["coverage"] == pytest.approx(0.93)

    project_payload = json.loads(project_payload_path.read_text(encoding="utf-8"))
    assert project_payload["recorded_at"] == entry["recorded_at"]
    assert project_payload["overall_coverage"] == pytest.approx(entry["overall"]["coverage"])


def test_export_trends_failure_raises_custom_error(tmp_path, quality_gate_script):
    summary_path = tmp_path / "coverage_summary.json"
    summary_path.write_text("{}\n", encoding="utf-8")
    history_path = tmp_path / "coverage_trends.json"
    snapshot_path = tmp_path / "coverage_trends_latest.json"
    project_payload_path = tmp_path / "coverage_projects_payload.json"

    with pytest.raises(quality_gate_script.CoverageTrendExportError):
        quality_gate_script._export_coverage_trends(
            summary_path=summary_path,
            history_path=history_path,
            snapshot_path=snapshot_path,
            project_payload_path=project_payload_path,
        )
