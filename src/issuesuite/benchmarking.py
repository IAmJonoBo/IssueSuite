"""Performance benchmarking harness for IssueSuite.

Provides comprehensive performance monitoring, metrics collection,
and benchmarking capabilities with reporting and analysis.
"""
from __future__ import annotations

import json
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable

from .logging import get_logger


@dataclass
class PerformanceMetric:
    """Individual performance metric."""
    name: str
    duration_ms: float
    timestamp: str
    context: Dict[str, Any]
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    operation: str
    total_duration_ms: float
    metrics: List[PerformanceMetric]
    summary: Dict[str, Any]
    timestamp: str
    environment: Dict[str, Any]


@dataclass
class BenchmarkConfig:
    """Configuration for benchmarking."""
    enabled: bool = False
    output_file: str = 'performance_report.json'
    collect_system_metrics: bool = True
    track_memory: bool = True
    track_cpu: bool = True
    warm_up_runs: int = 0
    benchmark_runs: int = 1


class PerformanceBenchmark:
    """Performance benchmarking and metrics collection."""
    
    def __init__(self, config: BenchmarkConfig, mock: bool = False):
        self.config = config
        self.mock = mock
        self.logger = get_logger()
        self._metrics: List[PerformanceMetric] = []
        self._active_timers: Dict[str, float] = {}
        self._system_monitor = None
        
        if config.enabled and config.collect_system_metrics and not mock:
            self._init_system_monitoring()
    
    def _init_system_monitoring(self) -> None:
        """Initialize system monitoring if available."""
        try:
            import psutil
            self._system_monitor = psutil
            self.logger.debug("System monitoring initialized")
        except ImportError:
            self.logger.warning("psutil not available - system metrics disabled")
            self._system_monitor = None
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        if not self._system_monitor or self.mock:
            return {}
        
        try:
            process = self._system_monitor.Process()
            memory_info = process.memory_info()
            
            return {
                'memory_rss_mb': memory_info.rss / 1024 / 1024,
                'memory_vms_mb': memory_info.vms / 1024 / 1024,
                'cpu_percent': process.cpu_percent(),
                'system_cpu_percent': self._system_monitor.cpu_percent(),
                'system_memory_percent': self._system_monitor.virtual_memory().percent,
            }
        except Exception as e:
            self.logger.debug(f"Failed to get system metrics: {e}")
            return {}
    
    @contextmanager
    def measure(self, operation: str, **context):
        """Context manager for measuring operation performance."""
        if not self.config.enabled:
            yield
            return
        
        start_time = time.perf_counter()
        start_metrics = self._get_system_metrics()
        
        try:
            self.logger.debug(f"Starting benchmark: {operation}")
            yield
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            end_metrics = self._get_system_metrics()
            
            # Calculate resource usage differences
            memory_usage = None
            cpu_usage = None
            
            if start_metrics and end_metrics:
                if 'memory_rss_mb' in end_metrics:
                    memory_usage = end_metrics['memory_rss_mb'] - start_metrics.get('memory_rss_mb', 0)
                if 'cpu_percent' in end_metrics:
                    cpu_usage = end_metrics['cpu_percent']
            
            metric = PerformanceMetric(
                name=operation,
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
                context=context,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage
            )
            
            self._metrics.append(metric)
            self.logger.log_performance(operation, duration_ms, **context)
    
    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        if self.config.enabled:
            self._active_timers[name] = time.perf_counter()
    
    def stop_timer(self, name: str, **context) -> Optional[float]:
        """Stop a named timer and record the metric."""
        if not self.config.enabled or name not in self._active_timers:
            return None
        
        start_time = self._active_timers.pop(name)
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        metric = PerformanceMetric(
            name=name,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context
        )
        
        self._metrics.append(metric)
        self.logger.log_performance(name, duration_ms, **context)
        return duration_ms
    
    def record_metric(self, name: str, duration_ms: float, **context) -> None:
        """Manually record a performance metric."""
        if not self.config.enabled:
            return
        
        metric = PerformanceMetric(
            name=name,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context
        )
        
        self._metrics.append(metric)
        self.logger.log_performance(name, duration_ms, **context)
    
    def benchmark_function(self, func: Callable, name: str, *args, **kwargs) -> BenchmarkResult:
        """Benchmark a function with multiple runs."""
        if not self.config.enabled:
            # Run once without benchmarking
            result = func(*args, **kwargs)
            return BenchmarkResult(
                operation=name,
                total_duration_ms=0.0,
                metrics=[],
                summary={},
                timestamp=datetime.now(timezone.utc).isoformat(),
                environment={}
            )
        
        self.logger.log_operation("benchmark_start", benchmark_name=name, 
                                 runs=self.config.benchmark_runs,
                                 warm_up_runs=self.config.warm_up_runs)
        
        # Warm-up runs
        for i in range(self.config.warm_up_runs):
            self.logger.debug(f"Warm-up run {i+1}/{self.config.warm_up_runs}")
            func(*args, **kwargs)
        
        # Benchmark runs
        run_metrics = []
        total_start = time.perf_counter()
        
        for i in range(self.config.benchmark_runs):
            with self.measure(f"{name}_run_{i+1}", run=i+1):
                result = func(*args, **kwargs)
        
        total_duration = (time.perf_counter() - total_start) * 1000
        
        # Get metrics for this benchmark
        run_metrics = [m for m in self._metrics if m.name.startswith(f"{name}_run_")]
        
        # Calculate summary statistics
        durations = [m.duration_ms for m in run_metrics]
        summary = {
            'runs': len(durations),
            'mean_ms': statistics.mean(durations) if durations else 0,
            'median_ms': statistics.median(durations) if durations else 0,
            'min_ms': min(durations) if durations else 0,
            'max_ms': max(durations) if durations else 0,
            'stddev_ms': statistics.stdev(durations) if len(durations) > 1 else 0,
            'total_ms': sum(durations),
        }
        
        # Environment info
        environment = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_metrics': self._get_system_metrics(),
        }
        
        benchmark_result = BenchmarkResult(
            operation=name,
            total_duration_ms=total_duration,
            metrics=run_metrics,
            summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=environment
        )
        
        self.logger.log_operation("benchmark_complete", benchmark_name=name, **summary)
        return benchmark_result
    
    def get_metrics(self, operation_filter: Optional[str] = None) -> List[PerformanceMetric]:
        """Get collected metrics, optionally filtered by operation name."""
        if operation_filter:
            return [m for m in self._metrics if operation_filter in m.name]
        return self._metrics.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all collected metrics."""
        if not self._metrics:
            return {}
        
        durations = [m.duration_ms for m in self._metrics]
        operations = {}
        
        # Group by operation
        for metric in self._metrics:
            op_name = metric.name
            if op_name not in operations:
                operations[op_name] = []
            operations[op_name].append(metric.duration_ms)
        
        # Calculate per-operation statistics
        operation_stats = {}
        for op_name, op_durations in operations.items():
            operation_stats[op_name] = {
                'count': len(op_durations),
                'total_ms': sum(op_durations),
                'mean_ms': statistics.mean(op_durations),
                'median_ms': statistics.median(op_durations),
                'min_ms': min(op_durations),
                'max_ms': max(op_durations),
                'stddev_ms': statistics.stdev(op_durations) if len(op_durations) > 1 else 0,
            }
        
        return {
            'total_metrics': len(self._metrics),
            'total_duration_ms': sum(durations),
            'overall_mean_ms': statistics.mean(durations),
            'overall_median_ms': statistics.median(durations),
            'operations': operation_stats,
            'environment': self._get_system_metrics(),
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }
    
    def generate_report(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        if not self.config.enabled:
            return {}
        
        report = {
            'benchmark_config': asdict(self.config),
            'metrics': [asdict(m) for m in self._metrics],
            'summary': self.get_summary(),
            'report_generated_at': datetime.now(timezone.utc).isoformat(),
        }
        
        output_file = output_path or self.config.output_file
        if output_file:
            try:
                Path(output_file).write_text(json.dumps(report, indent=2))
                self.logger.log_operation("performance_report_generated", 
                                        file_path=output_file,
                                        metric_count=len(self._metrics))
            except Exception as e:
                self.logger.log_error("Failed to write performance report", error=str(e))
        
        return report
    
    def clear_metrics(self) -> None:
        """Clear all collected metrics."""
        self._metrics.clear()
        self._active_timers.clear()
        self.logger.debug("Performance metrics cleared")
    
    def compare_benchmarks(self, other: 'PerformanceBenchmark') -> Dict[str, Any]:
        """Compare performance metrics with another benchmark."""
        if not self.config.enabled:
            return {}
        
        self_summary = self.get_summary()
        other_summary = other.get_summary()
        
        comparison = {
            'self_metrics': len(self._metrics),
            'other_metrics': len(other._metrics),
            'self_total_ms': self_summary.get('total_duration_ms', 0),
            'other_total_ms': other_summary.get('total_duration_ms', 0),
            'performance_ratio': 0,
            'operations_comparison': {},
        }
        
        if other_summary.get('total_duration_ms', 0) > 0:
            comparison['performance_ratio'] = (
                self_summary.get('total_duration_ms', 0) / 
                other_summary.get('total_duration_ms', 1)
            )
        
        # Compare individual operations
        self_ops = self_summary.get('operations', {})
        other_ops = other_summary.get('operations', {})
        
        common_ops = set(self_ops.keys()) & set(other_ops.keys())
        
        for op in common_ops:
            self_mean = self_ops[op]['mean_ms']
            other_mean = other_ops[op]['mean_ms']
            ratio = self_mean / other_mean if other_mean > 0 else 0
            
            comparison['operations_comparison'][op] = {
                'self_mean_ms': self_mean,
                'other_mean_ms': other_mean,
                'performance_ratio': ratio,
                'improvement_percent': ((other_mean - self_mean) / other_mean * 100) if other_mean > 0 else 0,
            }
        
        return comparison


def create_benchmark(config: BenchmarkConfig, mock: bool = False) -> PerformanceBenchmark:
    """Factory function to create a performance benchmark."""
    return PerformanceBenchmark(config, mock)


def benchmark_operation(operation: str, func: Callable, config: BenchmarkConfig, 
                       mock: bool = False, *args, **kwargs) -> BenchmarkResult:
    """Convenience function to benchmark a single operation."""
    benchmark = create_benchmark(config, mock)
    return benchmark.benchmark_function(func, operation, *args, **kwargs)


# Utility functions for performance analysis
def analyze_performance_trends(metrics: List[PerformanceMetric]) -> Dict[str, Any]:
    """Analyze performance trends in metrics."""
    if not metrics:
        return {}
    
    # Sort by timestamp
    sorted_metrics = sorted(metrics, key=lambda m: m.timestamp)
    
    # Group by operation
    operations = {}
    for metric in sorted_metrics:
        if metric.name not in operations:
            operations[metric.name] = []
        operations[metric.name].append(metric)
    
    analysis = {}
    
    for op_name, op_metrics in operations.items():
        durations = [m.duration_ms for m in op_metrics]
        
        # Simple trend analysis (first half vs second half)
        if len(durations) >= 4:
            midpoint = len(durations) // 2
            first_half_avg = statistics.mean(durations[:midpoint])
            second_half_avg = statistics.mean(durations[midpoint:])
            
            trend = "improving" if second_half_avg < first_half_avg else "degrading"
            trend_magnitude = abs(second_half_avg - first_half_avg) / first_half_avg * 100
            
            analysis[op_name] = {
                'trend': trend,
                'trend_magnitude_percent': trend_magnitude,
                'first_half_avg_ms': first_half_avg,
                'second_half_avg_ms': second_half_avg,
                'sample_count': len(durations),
            }
    
    return analysis


def get_performance_recommendations(summary: Dict[str, Any]) -> List[str]:
    """Get performance optimization recommendations based on metrics."""
    recommendations = []
    
    operations = summary.get('operations', {})
    
    # Find slowest operations
    slow_ops = [(name, stats['mean_ms']) for name, stats in operations.items()]
    slow_ops.sort(key=lambda x: x[1], reverse=True)
    
    if slow_ops:
        slowest_op, slowest_time = slow_ops[0]
        if slowest_time > 1000:  # > 1 second
            recommendations.append(
                f"Consider optimizing '{slowest_op}' operation (avg: {slowest_time:.1f}ms)"
            )
    
    # Check for high variance operations
    for op_name, stats in operations.items():
        if stats['stddev_ms'] > stats['mean_ms'] * 0.5:  # High variance
            recommendations.append(
                f"'{op_name}' shows high performance variance - investigate inconsistent behavior"
            )
    
    # Check overall performance
    total_time = summary.get('total_duration_ms', 0)
    if total_time > 10000:  # > 10 seconds
        recommendations.append(
            "Consider enabling concurrency for large roadmaps to improve overall performance"
        )
    
    return recommendations