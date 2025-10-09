---
id: ADR-0002
title: Automated Dependency Synchronization Enforcement
status: Accepted
decision_date: 2025-10-09
authors:
  - IssueSuite Maintainers
tags:
  - dependencies
  - ci
  - quality-gates
  - security
---

## Context

IssueSuite manages dependencies through multiple manifests:
- `pyproject.toml` for Python dependencies
- `uv.lock` for reproducible Python environments
- `docs/starlight/package.json` for documentation tooling
- `docs/starlight/package-lock.json` for reproducible Node.js environments

The project includes a `scripts/refresh-deps.sh` script that synchronizes lockfiles after manifest changes, and Renovate is configured to automatically invoke this script during dependency updates. However, manual changes to manifests (especially `pyproject.toml`) can result in stale lockfiles if developers forget to run the refresh script.

**Risk**: Lockfile drift creates environment inconsistencies between development, CI, and production. This can lead to:
- Silent dependency version changes between environments
- Build failures that are difficult to reproduce
- Supply chain security vulnerabilities from untracked transitive dependencies
- "Works on my machine" issues that waste developer time

**Current Gap**: While `refresh-deps.sh` exists and works correctly, there is no automated CI enforcement that validates lockfiles are synchronized with manifests on every pull request.

## Decision

We will enforce dependency synchronization through automated CI validation that:

1. **Blocks PRs with stale lockfiles** — A GitHub Actions workflow will run `scripts/refresh-deps.sh --check` on every pull request and block merge if lockfiles are out of sync with manifests.

2. **Provides clear remediation guidance** — Failure messages will instruct developers to run `./scripts/refresh-deps.sh` locally and commit the updated lockfiles.

3. **Validates both Python and Node.js dependencies** — The check covers `uv.lock` (Python) and `docs/starlight/package-lock.json` (Node.js).

4. **Runs early in the CI pipeline** — Lockfile validation runs before tests/quality gates to fail fast and save CI resources.

5. **Documents the workflow** — Update CONTRIBUTING.md and README.md with dependency management best practices.

## Implementation

### GitHub Actions Workflow

Create `.github/workflows/dependencies.yml`:

```yaml
name: Dependency Synchronization

on:
  pull_request:
    paths:
      - 'pyproject.toml'
      - 'uv.lock'
      - 'docs/starlight/package.json'
      - 'docs/starlight/package-lock.json'
      - 'scripts/refresh-deps.sh'

permissions:
  contents: read

jobs:
  check-lockfiles:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        run: pip install --user uv
      
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Validate lockfiles are synchronized
        run: ./scripts/refresh-deps.sh --check
```

### Testing Strategy

Add regression tests in `tests/test_refresh_deps.py` that validate:
- `--check` flag correctly detects stale lockfiles
- Script updates both Python and Node.js lockfiles
- Exit codes are correct for success/failure scenarios

### Documentation Updates

1. **README.md**: Add section on dependency management workflow
2. **CONTRIBUTING.md**: Create guide for adding/updating dependencies
3. **Next Steps.md**: Track ADR implementation progress

## Consequences

### Positive

- **Eliminates lockfile drift**: 100% of merged PRs will have synchronized lockfiles
- **Prevents supply chain attacks**: Lockfile bypass attack (RT-04) is mitigated
- **Improves reproducibility**: All environments use identical dependency versions
- **Reduces debugging time**: "Works on my machine" issues related to dependencies are eliminated
- **Fail-fast feedback**: Developers learn about lockfile issues before CI runs expensive tests

### Negative

- **Adds CI overhead**: ~30 seconds per PR for lockfile validation
- **Requires developer discipline**: Contributors must remember to run `refresh-deps.sh` after manifest changes
- **Tooling dependency**: Requires `uv` and `npm` to be available in CI (already the case)

### Neutral

- **Renovate unchanged**: Existing Renovate automation already calls `refresh-deps.sh`, so its behavior is unaffected
- **Local development optional**: Developers can still work without lockfiles locally, but CI enforces synchronization before merge

## Alternatives Considered

### 1. Git pre-commit hook

**Rejected**: Pre-commit hooks are optional and can be bypassed with `--no-verify`. CI enforcement is more reliable.

### 2. Lockfile-only installation in CI

**Rejected**: Would catch issues but not prevent them. Explicit validation provides clearer feedback.

### 3. Automatic lockfile regeneration in CI

**Rejected**: Would hide issues rather than surface them. We want developers to understand when they need to update lockfiles.

### 4. Bot auto-fixing lockfiles

**Rejected**: Adds complexity and could mask underlying issues. Developer awareness is valuable.

## Follow-up Tasks

- [x] Implement `.github/workflows/dependencies.yml`
- [x] Add regression tests in `tests/test_refresh_deps.py`
- [x] Update README.md with dependency workflow
- [x] Create CONTRIBUTING.md with detailed guidance
- [x] Add success metrics to quality dashboard (tracked in docs/RELEASE_CHECKLIST.md)
- [x] Document Renovate integration in ADR index (see docs/how-to/renovate-integration.mdx)

## Related ADRs

- ADR-0003: Hermetic Packaging Validation (proposed)
- ADR-0004: Development Environment Parity (proposed)

## References

- **Gap Analysis 2025**: docs/gap_analysis_2025.md — Identifies lockfile drift as critical gap (RT-04)
- **Renovate Config**: renovate.json — Existing automation that calls `refresh-deps.sh`
- **Refresh Script**: scripts/refresh-deps.sh — Implementation of lockfile synchronization
- **Red Team Report**: docs/red_team_report.md — Security assessment baseline
