import json
import os

from issuesuite.performance_report import generate_ci_reference_report


def test_generate_ci_reference_report(tmp_path, monkeypatch):
    monkeypatch.delenv("ISSUES_SUITE_MOCK", raising=False)
    output_path = tmp_path / "ci_performance_report.json"

    generated_path = generate_ci_reference_report(output_path)

    assert generated_path == output_path
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(data.get("metrics"), list)
    assert data["metrics"], "Expected benchmark metrics to be recorded"

    summary = data.get("summary", {})
    assert summary.get("total_metrics", 0) > 0
    assert isinstance(summary.get("operations"), dict)
    assert summary["operations"], "Expected per-operation statistics"

    # Environment flag should be restored by helper
    assert "ISSUES_SUITE_MOCK" not in os.environ or os.environ["ISSUES_SUITE_MOCK"] != "1"
