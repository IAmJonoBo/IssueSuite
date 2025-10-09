---
id: ADR-0004
title: GitHub App authentication with fallback JWT generation
status: Accepted
decision_date: 2025-10-15
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite relied on personal access tokens (PATs) for GitHub API authentication. GitHub Apps offer scoped permissions, audit trails, and higher rate limits, making them preferable for automation. However, JWT signing requires cryptographic dependencies (PyJWT) and the `gh` CLI, which may be unavailable in constrained environments.

## Decision

Extend `issuesuite.github_auth` to support GitHub App authentication via JWT token generation. When PyJWT or the `gh` CLI is unavailable, the module falls back to deterministic unsigned tokens or gracefully degrades to PAT-based auth. Configuration is driven by `issue_suite.config.yaml` under `github.app` with environment variable substitution for sensitive fields.

## Consequences

- GitHub App authentication is now supported with automatic fallback to PATs.
- JWT signing failures are logged but do not block syncs (fallback to PAT).
- Configuration secrets (app ID, private key path, installation ID) can reference environment variables.
- Token caching (`.github_app_token.json`) reduces API calls and respects file permissions (0600).

## Follow-up work

- Document GitHub App setup and permission scopes in tutorials.
- Add token refresh logic to handle expiration gracefully.
- Integrate token telemetry (success/failure rates) into observability dashboards.
