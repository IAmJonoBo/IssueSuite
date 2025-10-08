# Red Team Assessment — IssueSuite

_Date: 2025-10-06_

## Executive Summary

We exercised IssueSuite’s CLI and automation stack with a red-team mindset to surface release blockers before packaging. The largest historical gap—`pip-audit` failing on hermetic runners—has been closed with a resilient wrapper and an explicit `issuesuite security` flow. Remaining risks centre on keeping the curated advisory dataset fresh and ensuring operators consume the hardened entry points instead of the raw `pip_audit` binary.

## Attack Surface Review

- **Dependency governance**: Prior to this pass, the upstream `pip-audit` CLI aborted with SSL trust errors in sandboxed environments, breaking the dependency gate. We now ship `issuesuite.pip_audit_integration.ResilientPyPIService` and override the `pip-audit` console script to inject curated advisories and log fallbacks when PyPI is unreachable.【F:src/issuesuite/pip_audit_integration.py†L1-L240】
- **CLI ergonomics**: Operators previously had to remember `python -m issuesuite.dependency_audit`. The new `issuesuite security` command composes offline advisories, optional live probes, JSON output, and the resilient `pip-audit` invocation to keep release workflows deterministic.【F:src/issuesuite/cli.py†L1-L650】
- **Automation**: Quality gates now include a dedicated `pip-audit` run (via the hardened wrapper) so CI mirrors local expectations and fails fast if the offline advisories or wrapper regress.【F:scripts/quality_gates.py†L24-L60】

## Findings

| ID    | Severity | Description                                                                                                         | Remediation                                                                                                                                                                                                          |
| ----- | -------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RT-01 | Medium   | Offline advisories are static. Without scheduled refresh, new disclosures may be missed when runners lack internet. | ✅ Automated via `issuesuite.advisory_refresh` with CI gate enforcing dataset freshness.【F:src/issuesuite/advisory_refresh.py†L1-L236】【F:scripts/quality_gates.py†L20-L94】                                       |
| RT-02 | Low      | Operators might still call the legacy `python -m pip_audit` command, bypassing our wrapper.                         | ✅ Documented `issuesuite security --refresh-offline` workflow plus internal comms brief to steer operators to the wrapped entry points.【F:README.md†L40-L55】【F:docs/internal_comms_security_workflow.md†L1-L60】 |
| RT-03 | Low      | The resilient wrapper logs fallback reasons but does not currently emit telemetry.                                  | ✅ Telemetry spans emitted when fallbacks occur, surfacing degraded remote feeds via OTEL.【F:src/issuesuite/pip_audit_integration.py†L1-L240】                                                                      |

## Recommendations

1. **Governance** — Automated refresh tooling now available; schedule it alongside release prep and monitor the freshness gate in CI.
2. **Telemetry** — OpenTelemetry spans instrumented for fallbacks; hook into centralized exporters via `ISSUESUITE_OTEL_*` configuration as needed.
3. **Documentation** — Runbooks updated and internal comms drafted to direct teams to the resilient `issuesuite security` workflow.

## Test Evidence

- `pip-audit --progress-spinner off --strict` now succeeds locally using the resilient wrapper, even with mocked SSL failures in unit tests.【F:tests/test_pip_audit_integration.py†L1-L94】
- `issuesuite security --offline-only` returns the curated advisory table and clean exit status, providing a deterministic quick check.【F:tests/test_cli_extended.py†L190-L198】

## Next Actions

- [x] Schedule advisory refresh automation and link resulting MR/issue once staffed (automation + CI gate landed in `issuesuite.advisory_refresh`).
- [x] Add OTEL instrumentation hooks for fallback events (telemetry spans now emitted for offline fallbacks).
- [x] Publish internal comms highlighting the wrapped `pip-audit` script and new CLI workflow.
