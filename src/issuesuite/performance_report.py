"""Helpers for generating performance benchmarking reports in CI."""

from __future__ import annotations

import os
import textwrap
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from .benchmarking import BenchmarkConfig, create_benchmark
from .config import load_config
from .core import IssueSuite

_SAMPLE_CONFIG = textwrap.dedent(
    """
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
    behavior:
      dry_run_default: true
    ai: {}
    logging:
      json_enabled: true
      level: INFO
    performance:
      benchmarking: true
    """
).strip()

_SAMPLE_ISSUES = textwrap.dedent(
    """
    ## [slug: performance-smoke]
    ```yaml
    title: Performance smoke scenario
    labels: [maintenance]
    body: |
      Synthetic issue used to exercise the benchmarking harness.
    ```

    ## [slug: performance-preflight]
    ```yaml
    title: Preflight coverage scenario
    labels: [maintenance]
    milestone: Benchmark Validation
    body: |
      Ensures preflight paths are measured for performance budget enforcement.
    ```
    """
).strip()


@contextmanager
def _override_env(name: str, value: str) -> Iterator[None]:
    original = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original


def generate_ci_reference_report(output_path: str | Path | None = None) -> Path:
    """Generate a deterministic performance report suitable for CI gates."""

    target = (
        Path(output_path)
        if output_path is not None
        else Path("performance_report.json")
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory() as tmpdir, _override_env("ISSUES_SUITE_MOCK", "1"):
        workspace = Path(tmpdir)
        config_path = workspace / "issue_suite.config.yaml"
        issues_path = workspace / "ISSUES.md"

        config_path.write_text(_SAMPLE_CONFIG, encoding="utf-8")
        issues_path.write_text(_SAMPLE_ISSUES, encoding="utf-8")

        cfg = load_config(config_path)
        suite = IssueSuite(cfg)

        suite._benchmark_config = BenchmarkConfig(
            enabled=True,
            output_file=str(target),
            collect_system_metrics=False,
            track_memory=False,
            track_cpu=False,
        )
        suite._benchmark = create_benchmark(suite._benchmark_config, suite._mock)  # type: ignore[assignment]

        suite.sync(dry_run=True, update=False, respect_status=False, preflight=True)

    if not target.exists():
        raise RuntimeError(f"Failed to generate performance report at {target}")

    return target


__all__ = ["generate_ci_reference_report"]
