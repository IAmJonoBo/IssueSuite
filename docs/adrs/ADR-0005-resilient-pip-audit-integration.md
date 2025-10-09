---
id: ADR-0005
title: Resilient pip-audit integration with offline fallback
status: Accepted
decision_date: 2025-10-12
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite's quality gates included `pip-audit` for vulnerability scanning, but hermetic environments (e.g., air-gapped CI runners, restrictive networks) often experienced hangs or SSL failures. Without a fallback, the dependency gate would block deployments. We needed a resilient wrapper that gracefully degrades to curated offline advisories.

## Decision

Introduce `issuesuite.pip_audit_integration` to wrap `pip-audit` with configurable timeout, network error detection, and automatic fallback to offline advisories (`src/issuesuite/data/security_advisories.json`). The CLI exposes `issuesuite security` with flags like `--pip-audit`, `--pip-audit-disable-online`, and `--refresh-offline` to control execution. The quality gate script routes pip-audit through this wrapper.

## Consequences

- Dependency scans complete reliably in offline/hermetic environments.
- Offline advisory dataset requires periodic refresh (`issuesuite.advisory_refresh`).
- Telemetry logs fallback events (network failures, timeouts) for observability.
- The wrapper preserves stdout/stderr streams for debugging.

## Follow-up work

- Automate offline advisory refresh in CI (nightly or weekly).
- Emit OpenTelemetry spans for pip-audit execution metrics.
- Document how to curate and refresh `security_advisories.json`.
