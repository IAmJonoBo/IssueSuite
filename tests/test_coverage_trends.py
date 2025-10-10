import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from issuesuite.coverage_trends import export_trends


def write_summary(path: Path, modules: list[dict[str, object]]) -> None:
    payload = {
        "generated_at": "2025-10-09T00:00:00+00:00",
        "report": "coverage.xml",
        "modules": modules,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_export_trends_creates_history_and_payload(tmp_path: Path) -> None:
    summary_path = tmp_path / "coverage_summary.json"
    history_path = tmp_path / "coverage_trends.json"
    snapshot_path = tmp_path / "coverage_trends_latest.json"
    project_path = tmp_path / "coverage_projects_payload.json"

    write_summary(
        summary_path,
        [
            {
                "module": "src/issuesuite/core.py",
                "coverage": 0.91,
                "threshold": 0.9,
                "meets_threshold": True,
            },
            {
                "module": "src/issuesuite/cli.py",
                "coverage": 0.87,
                "threshold": 0.9,
                "meets_threshold": False,
            },
        ],
    )

    entry = export_trends(
        summary_path=summary_path,
        history_path=history_path,
        snapshot_path=snapshot_path,
        project_payload_path=project_path,
        max_records=5,
        now=datetime(2025, 10, 9, 12, 30, tzinfo=timezone.utc),
    )

    assert pytest.approx(entry["overall"]["coverage"], rel=1e-6) == 0.89
    assert entry["overall"]["meets_target"] is True
    assert entry["regressions"] == []
    assert entry["improvements"] == []

    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["recorded_at"] == entry["recorded_at"]

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot == entry

    project_payload = json.loads(project_path.read_text(encoding="utf-8"))
    assert project_payload["status"] == "off_track"
    assert project_payload["failing_modules"] == ["src/issuesuite/cli.py"]
    assert project_payload["regressions"] == []
    assert project_payload["overall_coverage"] == entry["overall"]["coverage"]


def test_export_trends_computes_deltas_from_history(tmp_path: Path) -> None:
    summary_path = tmp_path / "coverage_summary.json"
    history_path = tmp_path / "coverage_trends.json"
    snapshot_path = tmp_path / "coverage_trends_latest.json"
    project_path = tmp_path / "coverage_projects_payload.json"

    previous_entry = {
        "recorded_at": "2025-10-08T10:00:00+00:00",
        "overall": {
            "coverage": 0.92,
            "target": 0.85,
            "meets_target": True,
            "delta": None,
        },
        "modules": [
            {
                "module": "src/issuesuite/core.py",
                "coverage": 0.93,
                "threshold": 0.9,
                "meets_threshold": True,
                "delta": None,
                "trend": "steady",
            },
            {
                "module": "src/issuesuite/cli.py",
                "coverage": 0.91,
                "threshold": 0.9,
                "meets_threshold": True,
                "delta": None,
                "trend": "steady",
            },
        ],
        "regressions": [],
        "improvements": [],
        "summary_generated_at": "2025-10-08T09:50:00+00:00",
    }
    history_path.write_text(json.dumps([previous_entry]), encoding="utf-8")

    write_summary(
        summary_path,
        [
            {
                "module": "src/issuesuite/core.py",
                "coverage": 0.95,
                "threshold": 0.9,
                "meets_threshold": True,
            },
            {
                "module": "src/issuesuite/cli.py",
                "coverage": 0.88,
                "threshold": 0.9,
                "meets_threshold": False,
            },
        ],
    )

    entry = export_trends(
        summary_path=summary_path,
        history_path=history_path,
        snapshot_path=snapshot_path,
        project_payload_path=project_path,
        max_records=5,
        now=datetime(2025, 10, 9, 8, tzinfo=timezone.utc),
    )

    assert pytest.approx(entry["overall"]["coverage"], rel=1e-6) == 0.915
    assert pytest.approx(entry["overall"]["delta"], rel=1e-6) == -0.004999999999999893

    core_entry = next(
        m for m in entry["modules"] if m["module"] == "src/issuesuite/core.py"
    )
    cli_entry = next(
        m for m in entry["modules"] if m["module"] == "src/issuesuite/cli.py"
    )

    assert pytest.approx(core_entry["delta"], rel=1e-6) == 0.020000000000000018
    assert pytest.approx(cli_entry["delta"], rel=1e-6) == -0.029999999999999916
    assert "src/issuesuite/cli.py" in entry["regressions"]
    assert "src/issuesuite/core.py" in entry["improvements"]

    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(history) == 2
    assert history[-1]["recorded_at"] == entry["recorded_at"]

    project_payload = json.loads(project_path.read_text(encoding="utf-8"))
    assert project_payload["status"] == "off_track"
    assert "src/issuesuite/cli.py" in project_payload["regressions"]
    assert project_payload["improvements"] == ["src/issuesuite/core.py"]
