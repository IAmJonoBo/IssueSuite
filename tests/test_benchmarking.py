import json
import time

import pytest

from issuesuite.benchmarking import (
    SLOW_OPERATION_MS,
    BenchmarkConfig,
    BenchmarkResult,
    PerformanceBenchmark,
    PerformanceMetric,
    analyze_performance_trends,
    benchmark_operation,
    check_performance_budget,
    create_benchmark,
    get_performance_recommendations,
)


def test_benchmark_config():
    """Test BenchmarkConfig initialization."""
    config = BenchmarkConfig(
        enabled=True,
        output_file="test_report.json",
        collect_system_metrics=True,
        track_memory=True,
        track_cpu=True,
        warm_up_runs=2,
        benchmark_runs=5,
    )

    assert config.enabled is True
    assert config.output_file == "test_report.json"
    assert config.collect_system_metrics is True
    assert config.track_memory is True
    assert config.track_cpu is True
    assert config.warm_up_runs == 2
    assert config.benchmark_runs == 5


def test_benchmark_config_defaults():
    """Test BenchmarkConfig with defaults."""
    config = BenchmarkConfig()

    assert config.enabled is False
    assert config.output_file == "performance_report.json"
    assert config.collect_system_metrics is True
    assert config.track_memory is True
    assert config.track_cpu is True
    assert config.warm_up_runs == 0
    assert config.benchmark_runs == 1


def test_performance_benchmark_disabled():
    """Test PerformanceBenchmark when disabled."""
    config = BenchmarkConfig(enabled=False)
    benchmark = PerformanceBenchmark(config)

    # Measure should not record anything when disabled
    with benchmark.measure("test_operation", param1="value1"):
        time.sleep(0.01)

    metrics = benchmark.get_metrics()
    assert len(metrics) == 0


def test_performance_benchmark_enabled():
    """Test PerformanceBenchmark when enabled."""
    config = BenchmarkConfig(enabled=True)
    benchmark = PerformanceBenchmark(config, mock=True)

    # Measure should record metrics when enabled
    with benchmark.measure("test_operation", param1="value1"):
        time.sleep(0.01)

    metrics = benchmark.get_metrics()
    assert len(metrics) == 1

    metric = metrics[0]
    assert metric.name == "test_operation"
    assert metric.duration_ms > 0
    assert metric.context["param1"] == "value1"
    assert metric.timestamp is not None


def test_timer_functions():
    """Test start_timer and stop_timer functions."""
    config = BenchmarkConfig(enabled=True)
    benchmark = PerformanceBenchmark(config, mock=True)

    # Start and stop timer
    benchmark.start_timer("test_timer")
    time.sleep(0.01)
    duration = benchmark.stop_timer("test_timer", context_param="test")

    assert duration is not None
    assert duration > 0

    metrics = benchmark.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "test_timer"
    assert metrics[0].context["context_param"] == "test"


def test_timer_functions_disabled():
    """Test timer functions when benchmarking is disabled."""
    config = BenchmarkConfig(enabled=False)
    benchmark = PerformanceBenchmark(config)

    benchmark.start_timer("disabled_timer")
    duration = benchmark.stop_timer("disabled_timer")

    assert duration is None
    assert len(benchmark.get_metrics()) == 0


def test_record_metric():
    """Test manual metric recording."""
    config = BenchmarkConfig(enabled=True)
    benchmark = PerformanceBenchmark(config, mock=True)

    benchmark.record_metric("manual_metric", 123.45, test_param="test_value")

    metrics = benchmark.get_metrics()
    assert len(metrics) == 1

    metric = metrics[0]
    assert metric.name == "manual_metric"
    assert metric.duration_ms == 123.45
    assert metric.context["test_param"] == "test_value"


def test_check_performance_budget(tmp_path):
    report = tmp_path / "performance_report.json"
    report.write_text(
        json.dumps(
            {
                "metrics": [
                    {"name": "fast-op", "duration_ms": 10},
                    {"name": "near-threshold", "duration_ms": SLOW_OPERATION_MS - 1},
                ]
            }
        )
    )

    check_performance_budget(report)

    report.write_text(
        json.dumps(
            {
                "metrics": [
                    {"name": "slow-op", "duration_ms": SLOW_OPERATION_MS + 5},
                ]
            }
        )
    )

    with pytest.raises(RuntimeError):
        check_performance_budget(report)


def test_benchmark_function():
    """Test function benchmarking."""
    config = BenchmarkConfig(enabled=True, warm_up_runs=1, benchmark_runs=3)
    benchmark = PerformanceBenchmark(config, mock=True)

    def test_function(x, y):
        time.sleep(0.005)  # Simulate work
        return x + y

    result = benchmark.benchmark_function(test_function, "add_operation", 5, 3)

    assert isinstance(result, BenchmarkResult)
    assert result.operation == "add_operation"
    assert result.total_duration_ms > 0
    assert len(result.metrics) == 3  # 3 benchmark runs
    assert result.summary["runs"] == 3
    assert result.summary["mean_ms"] > 0
    assert result.summary["min_ms"] > 0
    assert result.summary["max_ms"] > 0


def test_benchmark_function_disabled():
    """Test function benchmarking when disabled."""
    config = BenchmarkConfig(enabled=False)
    benchmark = PerformanceBenchmark(config)

    def test_function():
        return "result"

    result = benchmark.benchmark_function(test_function, "disabled_op")

    assert isinstance(result, BenchmarkResult)
    assert result.operation == "disabled_op"
    assert result.total_duration_ms == 0.0
    assert len(result.metrics) == 0


def test_get_metrics_with_filter():
    """Test getting metrics with operation filter."""
    config = BenchmarkConfig(enabled=True)
    benchmark = PerformanceBenchmark(config, mock=True)

    benchmark.record_metric("operation_1", 100.0)
    benchmark.record_metric("operation_2", 200.0)
    benchmark.record_metric("operation_1_variant", 150.0)

    # Filter by operation name
    op1_metrics = benchmark.get_metrics("operation_1")
    assert len(op1_metrics) == 2  # operation_1 and operation_1_variant

    op2_metrics = benchmark.get_metrics("operation_2")
    assert len(op2_metrics) == 1

    all_metrics = benchmark.get_metrics()
    assert len(all_metrics) == 3


def test_get_summary():
    """Test summary generation."""
    config = BenchmarkConfig(enabled=True)
    benchmark = PerformanceBenchmark(config, mock=True)

    benchmark.record_metric("op1", 100.0)
    benchmark.record_metric("op1", 120.0)
    benchmark.record_metric("op2", 200.0)

    summary = benchmark.get_summary()

    assert summary["total_metrics"] == 3
    assert summary["total_duration_ms"] == 420.0
    assert summary["overall_mean_ms"] == 140.0

    # Check per-operation statistics
    assert "op1" in summary["operations"]
    assert "op2" in summary["operations"]

    op1_stats = summary["operations"]["op1"]
    assert op1_stats["count"] == 2
    assert op1_stats["total_ms"] == 220.0
    assert op1_stats["mean_ms"] == 110.0


def test_generate_report(tmp_path):
    """Test report generation."""
    output_file = tmp_path / "test_report.json"
    config = BenchmarkConfig(enabled=True, output_file=str(output_file))
    benchmark = PerformanceBenchmark(config, mock=True)

    benchmark.record_metric("test_op", 100.0, context="test")

    report = benchmark.generate_report()

    # Check report structure
    assert "benchmark_config" in report
    assert "metrics" in report
    assert "summary" in report
    assert "report_generated_at" in report

    # Check file was written
    assert output_file.exists()

    # Verify file contents
    file_data = json.loads(output_file.read_text())
    assert file_data == report


def test_generate_report_disabled():
    """Test report generation when disabled."""
    config = BenchmarkConfig(enabled=False)
    benchmark = PerformanceBenchmark(config)

    report = benchmark.generate_report()
    assert report == {}


def test_clear_metrics():
    """Test metrics clearing."""
    config = BenchmarkConfig(enabled=True)
    benchmark = PerformanceBenchmark(config, mock=True)

    benchmark.record_metric("test", 100.0)
    assert len(benchmark.get_metrics()) == 1

    benchmark.clear_metrics()
    assert len(benchmark.get_metrics()) == 0


def test_compare_benchmarks():
    """Test benchmark comparison."""
    config = BenchmarkConfig(enabled=True)
    benchmark1 = PerformanceBenchmark(config, mock=True)
    benchmark2 = PerformanceBenchmark(config, mock=True)

    # Benchmark 1 - slower
    benchmark1.record_metric("shared_op", 200.0)
    benchmark1.record_metric("shared_op", 220.0)

    # Benchmark 2 - faster
    benchmark2.record_metric("shared_op", 100.0)
    benchmark2.record_metric("shared_op", 120.0)

    comparison = benchmark1.compare_benchmarks(benchmark2)

    assert comparison["self_metrics"] == 2
    assert comparison["other_metrics"] == 2
    assert comparison["performance_ratio"] > 1  # benchmark1 is slower

    # Check operation comparison
    assert "shared_op" in comparison["operations_comparison"]
    op_comp = comparison["operations_comparison"]["shared_op"]
    assert op_comp["self_mean_ms"] == 210.0
    assert op_comp["other_mean_ms"] == 110.0
    assert op_comp["improvement_percent"] < 0  # benchmark1 is worse


def test_factory_function():
    """Test factory function for creating benchmarks."""
    config = BenchmarkConfig(enabled=True)
    benchmark = create_benchmark(config, mock=True)

    assert isinstance(benchmark, PerformanceBenchmark)
    assert benchmark.config == config
    assert benchmark.mock is True


def test_benchmark_operation_function():
    """Test convenience function for benchmarking operations."""
    config = BenchmarkConfig(enabled=True, benchmark_runs=2)

    def simple_op(x):
        time.sleep(0.001)
        return x * 2

    result = benchmark_operation("multiply", simple_op, config, True, 5)

    assert isinstance(result, BenchmarkResult)
    assert result.operation == "multiply"
    assert result.summary["runs"] == 2


def test_analyze_performance_trends():
    """Test performance trend analysis."""
    metrics = [
        PerformanceMetric("op1", 100.0, "2025-01-01T10:00:00Z", {}),
        PerformanceMetric("op1", 110.0, "2025-01-01T10:01:00Z", {}),
        PerformanceMetric("op1", 90.0, "2025-01-01T10:02:00Z", {}),
        PerformanceMetric("op1", 85.0, "2025-01-01T10:03:00Z", {}),
    ]

    analysis = analyze_performance_trends(metrics)

    assert "op1" in analysis
    op_analysis = analysis["op1"]
    assert op_analysis["trend"] == "improving"  # Getting faster over time
    assert op_analysis["sample_count"] == 4


def test_get_performance_recommendations():
    """Test performance recommendation generation."""
    summary = {
        "operations": {
            "slow_operation": {"mean_ms": 2000.0, "stddev_ms": 100.0},
            "variable_operation": {"mean_ms": 500.0, "stddev_ms": 300.0},
            "fast_operation": {"mean_ms": 50.0, "stddev_ms": 5.0},
        },
        "total_duration_ms": 15000.0,
    }

    recommendations = get_performance_recommendations(summary)

    # Should recommend optimizing slow operation
    assert any("slow_operation" in rec for rec in recommendations)

    # Should note high variance in variable_operation
    assert any("variable_operation" in rec and "variance" in rec for rec in recommendations)

    # Should suggest concurrency for long total time
    assert any("concurrency" in rec for rec in recommendations)
