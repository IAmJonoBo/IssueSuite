import json
from pathlib import Path

from issuesuite import IssueSuite, load_config

CONFIG_WITH_BENCHMARKING = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: false
  level: INFO
performance:
  benchmarking: true
"""

CONFIG_WITHOUT_BENCHMARKING = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: false
  level: INFO
performance:
  benchmarking: false
"""

ISSUES = """## [slug: test-issue]
```yaml
title: Test Issue
labels: [bug]
body: |
  Test issue body
```

## [slug: another-issue]
```yaml
title: Another Issue
labels: [enhancement]
body: |
  Another issue body
```
"""


def test_sync_with_benchmarking_enabled(monkeypatch, tmp_path):
    """Test sync with performance benchmarking enabled."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_BENCHMARKING)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify benchmarking is enabled
    assert cfg.performance_benchmarking is True
    assert suite._benchmark_config.enabled is True

    # Run sync - should collect performance metrics
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)

    # Should complete successfully
    assert summary["totals"]["specs"] == 2
    assert summary["totals"]["created"] == 2

    # Check that metrics were collected
    metrics = suite._benchmark.get_metrics()
    assert len(metrics) > 0

    # Should have performance report
    report_path = Path("performance_report.json")
    assert report_path.exists()

    # Verify report content
    report_data = json.loads(report_path.read_text())
    assert "benchmark_config" in report_data
    assert "metrics" in report_data
    assert "summary" in report_data

    # Cleanup
    report_path.unlink()


def test_sync_with_benchmarking_disabled(monkeypatch, tmp_path):
    """Test sync with performance benchmarking disabled."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITHOUT_BENCHMARKING)

    # Set mock mode
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify benchmarking is disabled
    assert cfg.performance_benchmarking is False
    assert suite._benchmark_config.enabled is False

    # Run sync - should not collect performance metrics
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)

    # Should complete successfully
    assert summary["totals"]["specs"] == 2
    assert summary["totals"]["created"] == 2

    # Should not collect metrics when disabled
    metrics = suite._benchmark.get_metrics()
    assert len(metrics) == 0

    # Should not create performance report
    report_path = Path("performance_report.json")
    assert not report_path.exists()


def test_benchmarking_config_loading(tmp_path):
    """Test loading benchmarking configuration from config file."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG_WITH_BENCHMARKING)

    cfg = load_config(cfg_path)

    # Verify benchmarking settings are loaded correctly
    assert cfg.performance_benchmarking is True


def test_benchmarking_config_defaults(tmp_path):
    """Test default benchmarking configuration when not specified."""
    config_without_performance_section = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
"""

    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(config_without_performance_section)

    cfg = load_config(cfg_path)

    # Verify default benchmarking settings
    assert cfg.performance_benchmarking is False


def test_performance_metrics_collection(monkeypatch, tmp_path):
    """Test detailed performance metrics collection."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_BENCHMARKING)

    # Set mock mode and enable JSON logging to see metrics
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Run sync
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)

    # Get collected metrics
    metrics = suite._benchmark.get_metrics()

    # Should have metrics for different operations
    metric_names = [m.name for m in metrics]
    assert "sync_total" in metric_names
    assert "parse_specs" in metric_names
    assert "fetch_existing_issues" in metric_names
    assert "process_specs" in metric_names

    # Check that metrics have proper structure
    for metric in metrics:
        assert metric.name is not None
        assert metric.duration_ms >= 0
        assert metric.timestamp is not None
        assert isinstance(metric.context, dict)

    # Get summary statistics
    bench_summary = suite._benchmark.get_summary()
    assert bench_summary["total_metrics"] > 0
    assert bench_summary["total_duration_ms"] > 0
    assert "operations" in bench_summary


def test_benchmarking_with_preflight(monkeypatch, tmp_path):
    """Test benchmarking includes preflight operations."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_BENCHMARKING)

    # Set mock mode
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Run sync with preflight
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=True)

    # Should include preflight metrics
    metrics = suite._benchmark.get_metrics()
    metric_names = [m.name for m in metrics]
    assert "preflight_setup" in metric_names


def test_performance_report_generation(monkeypatch, tmp_path):
    """Test comprehensive performance report generation."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_BENCHMARKING)

    # Set mock mode
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Run multiple operations to generate interesting metrics
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)

    # Generate additional report
    custom_report_path = tmp_path / "custom_report.json"
    report = suite._benchmark.generate_report(str(custom_report_path))

    # Verify report structure
    assert isinstance(report, dict)
    assert "benchmark_config" in report
    assert "metrics" in report
    assert "summary" in report
    assert "report_generated_at" in report

    # Verify custom report file
    assert custom_report_path.exists()
    custom_data = json.loads(custom_report_path.read_text())
    assert custom_data == report

    # Verify summary contains expected data
    summary = report["summary"]
    assert "total_metrics" in summary
    assert "operations" in summary
    assert "environment" in summary


def test_benchmarking_error_handling(monkeypatch, tmp_path, capsys):
    """Test error handling in benchmarking system."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_BENCHMARKING)

    # Set mock mode
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Try to generate report to invalid location
    invalid_path = "/invalid/path/report.json"
    report = suite._benchmark.generate_report(invalid_path)

    # Should handle error gracefully
    assert isinstance(report, dict)

    # Should log error but continue working
    captured = capsys.readouterr()
    # Error handling is internal, sync should still work
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    assert summary["totals"]["specs"] == 2
