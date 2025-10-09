---
id: ADR-0008
title: Accept transitive dev dependency vulnerabilities with periodic review
status: Accepted
decision_date: 2025-10-09
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite's quality gates include pip-audit to detect vulnerabilities in Python dependencies. However, the gate frequently fails due to vulnerabilities in transitive dev/test dependencies (certifi, cryptography, jinja2, twisted, urllib3, etc.) that are not part of the runtime application.

These dependencies are:
- Only present in development environments
- Not shipped with the package distribution
- Not executable in production deployments
- Often from testing frameworks (pytest, detect-secrets, bandit, etc.)

Blocking CI on dev dependency vulnerabilities creates friction without materially improving security posture, since:
- Users install IssueSuite via `pip install issuesuite` (no dev deps)
- CI runs in ephemeral containers  
- Dev environments are not production attack surfaces

## Decision

Remove the pip-audit quality gate from the standard gate suite while maintaining the core dependency_audit gate (which checks only runtime dependencies against curated advisories). The Dependencies gate provides:
- Focused runtime dependency scanning
- Offline advisory fallback for hermetic environments  
- Curated allowlist for accepted risks
- Faster execution without network timeouts

The team will continue to monitor dev dependencies via:
- Renovate automated updates
- Periodic pip-audit runs (outside CI gates)
- Security-focused code reviews

## Consequences

- CI quality gates complete faster and more reliably
- No false failures from transitive dev dependencies
- Runtime application security remains protected via dependency_audit gate
- Dev dependency security monitored via Renovate and periodic reviews
- Cleaner separation between runtime and dev security concerns

## Follow-up work

- Configure Renovate to auto-merge dev dependency security updates
- Add monthly review task for pip-audit findings
- Document which vulnerabilities affect only dev environments
- Consider separate security scan for runtime vs dev dependencies
