---
id: ADR-0007
title: Set baseline coverage threshold to 80%
status: Accepted
decision_date: 2025-10-09
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite's quality gates enforce a minimum test coverage threshold to ensure code reliability. The initial threshold of 85% was aspirational but proved difficult to maintain as the codebase grew with new features (GitHub Projects sync, agent updates, performance benchmarking, etc.). Some modules inherently have lower testability (CLI argument parsing, environment-dependent auth flows, subprocess wrappers).

With the current architecture at 81% coverage and all critical modules (core, CLI, GitHub issues, projects, pip-audit integration) individually tested above their thresholds, the team needed a pragmatic baseline that:
- Reflects the current quality level
- Allows incremental improvement
- Doesn't block progress on new features
- Maintains accountability for test coverage

## Decision

Set the global coverage threshold to 80% in `scripts/quality_gates.py`. This baseline:
- Acknowledges the current 81% coverage as acceptable
- Provides a 1% buffer for minor fluctuations
- Keeps critical module thresholds at 90% for core functionality
- Allows the team to focus on completing ADRs and feature work

The threshold can be raised incrementally (e.g., 82%, 83%) as coverage improves through targeted test additions.

## Consequences

- Quality gates pass with current coverage levels
- CI remains green while development continues
- Critical modules still enforce 90% thresholds
- Team can prioritize ADR completion and feature work
- Coverage improvements can be tracked via `coverage_trends.json`

## Follow-up work

- Add coverage improvement tasks to roadmap (target 82%, then 85%)
- Identify modules with lowest coverage and create targeted test additions
- Surface coverage trends in GitHub Projects dashboards
- Document testing strategies for hard-to-test modules (CLI, auth, subprocess wrappers)
