---
id: ADR-0006
title: Lightweight performance benchmarking and budget enforcement
status: Accepted
decision_date: 2025-10-18
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite syncs grew in complexity (parsing, GitHub API calls, hash computation) with no instrumentation to detect performance regressions. We needed a lightweight benchmarking layer that could capture wall-clock timings and system metrics without requiring profiling tools in CI.

## Decision

Introduce `issuesuite.benchmarking` to optionally capture operation timings (parse specs, fetch issues, process specs, save hashes) and system metrics (CPU, memory). A companion `issuesuite.performance_report` module generates deterministic `performance_report.json` by running syncs in mock mode against synthetic roadmaps. The quality gate script enforces budgets via `issuesuite.benchmarking --check`.

## Consequences

- Performance data is emitted to `performance_report.json` when enabled.
- CI can gate on performance budgets to prevent regressions.
- Metrics are approximate (wall-clock only); use `py-spy` for deep profiling.
- Benchmarks run in mock mode for deterministic results across environments.

## Follow-up work

- Integrate performance trends into GitHub Projects dashboards.
- Add OpenTelemetry tracing for distributed sync operations.
- Document how to refresh performance baselines after intentional changes.
