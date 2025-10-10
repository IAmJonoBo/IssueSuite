# Internal Announcement — IssueSuite Security Workflow

> **📚 ARCHIVED DOCUMENT**
>
> This internal announcement from 2025-10-06 describes security workflow changes that are now part of standard documentation.
>
> **See current documentation:**
> - [Environment Variables Reference](../starlight/src/content/docs/reference/environment-variables.mdx)
> - [Release Checklist](../RELEASE_CHECKLIST.md)

_Date: 2025-10-06_

## Summary

- A lightweight `sitecustomize.py` now preloads the resilient pip-audit service so even `python -m pip_audit --strict` honours the offline dataset and 60s timeout by default.
- `issuesuite security` now supports `--refresh-offline` to update the curated advisory dataset before scanning.
- A resilient `pip-audit` wrapper is installed with the package; invoking `issuesuite security --pip-audit` forwards to the wrapped entry point with hermetic-safe defaults.
- Offline advisories are refreshed via `python -m issuesuite.advisory_refresh --refresh --check`, which merges OSV metadata and enforces freshness through CI quality gates.
- Accepted-risk vulnerabilities now flow through a governed allowlist (`src/issuesuite/data/security_allowlist.json`) so unavoidable upstream issues (for example GHSA-4xh5-x5gv-qwph affecting pip) surface with context while CI remains green until upstream patches land.

## Why it matters

- Hermetic builders no longer fail on SSL trust issues because the wrapper automatically falls back to curated advisories.
- Operators receive telemetry breadcrumbs whenever the wrapper relies on offline data so incidents tied to upstream outages are visible in observability stacks.
- Packaging runbooks can rely on a single command (`issuesuite security`) for both JSON reporting and pip-audit parity.

## Required Actions

1. Update internal release runbooks to call:
   ```bash
   python -m issuesuite.advisory_refresh --refresh --check --max-age-days 30
   issuesuite security --pip-audit --pip-audit-arg --format --pip-audit-arg json
   ```
2. Configure OTEL exporters where available by setting `ISSUESUITE_OTEL_EXPORTER=console` (or `otlp`) before running the security workflow.
3. Archive previous instructions pointing to `python -m pip_audit`; the IssueSuite wrapper should be the only supported entry point going forward.
4. When debugging legacy scripts that still shell out to `python -m pip_audit`, rely on the bundled `sitecustomize.py` shim for consistent offline behaviour, but prefer the `issuesuite security --pip-audit` wrapper for CI and automation.

## Contacts

- Security Engineering: security@example.com
- Release Management: releases@example.com
- Maintainers: @IAmJonoBo
