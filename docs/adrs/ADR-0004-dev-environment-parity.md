---
id: ADR-0004
title: Development Environment Parity
status: Accepted
decision_date: 2025-10-09
authors:
  - IssueSuite Maintainers
tags:
  - developer-experience
  - ci
  - quality-gates
  - tooling
---

## Context

IssueSuite enforces quality gates through multiple tools:
- `ruff` for linting and formatting
- `mypy` for type checking
- `pytest` for testing
- `bandit` for security scanning
- `detect-secrets` for secret detection

These tools are invoked both locally (via `nox` sessions) and in CI (via GitHub Actions). However, version mismatches between local and CI environments can lead to "works on my machine" failures:

- Local `ruff` version differs from CI, causing format disputes
- `mypy` detects different issues with different versions
- Tests pass locally but fail in CI due to dependency version differences
- Pre-commit hooks exist in `.githooks/` but aren't documented or enforced

**Current Gap**: While CI enforces quality gates consistently, there's no mechanism to ensure local development environments match CI configuration. This leads to:
- Wasted CI cycles from preventable failures
- Developer frustration when CI rejects passing local builds
- Inconsistent code quality enforcement
- Tribal knowledge about "correct" tool versions

## Decision

We will establish development environment parity through:

1. **Lockfile-based tool installation** — Quality gate tools are pinned in `pyproject.toml` optional dependencies and installed from `uv.lock`.

2. **Pre-commit hook automation** — Provide setup script that installs Git hooks to run critical checks before commit.

3. **Environment validation command** — Add `issuesuite doctor` CLI command that validates local environment matches CI.

4. **Documentation** — Clear CONTRIBUTING.md guide explaining setup process.

5. **CI parity checks** — Optional CI job that verifies tool versions match expected versions.

## Implementation

### 1. Tool Version Pinning

Already done in `pyproject.toml`:
```toml
optional-dependencies.dev = [
  "ruff==0.14",  # Pinned exact version
  "mypy>=1.8",
  ...
]
```

### 2. Pre-commit Hook Setup Script

Create `scripts/setup-dev-env.sh`:

```bash
#!/usr/bin/env bash
# Install Git hooks and configure development environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Setting up IssueSuite development environment..."

# 1. Install Git hooks
if [ -d "${PROJECT_ROOT}/.git" ]; then
  echo "Installing Git hooks..."
  git config core.hooksPath "${PROJECT_ROOT}/.githooks"
  chmod +x "${PROJECT_ROOT}/.githooks"/*
  echo "✓ Git hooks configured"
else
  echo "⚠ Not a Git repository, skipping hook setup"
fi

# 2. Validate Python environment
if ! python -m issuesuite --version >/dev/null 2>&1; then
  echo "⚠ IssueSuite not installed. Run: pip install -e .[dev,all]"
fi

# 3. Validate lockfiles
if command -v uv >/dev/null 2>&1; then
  echo "Checking lockfile synchronization..."
  if ! "${PROJECT_ROOT}/scripts/refresh-deps.sh" --check; then
    echo "⚠ Lockfiles out of sync. Run: ./scripts/refresh-deps.sh"
  else
    echo "✓ Lockfiles synchronized"
  fi
fi

# 4. Validate nox installation
if ! command -v nox >/dev/null 2>&1; then
  echo "⚠ nox not installed. Install: pip install nox"
else
  echo "✓ nox available"
fi

echo ""
echo "Development environment ready!"
echo "Run 'nox -s tests lint typecheck' to validate your setup"
```

### 3. Enhance `issuesuite doctor` Command

Expand existing setup wizard in `src/issuesuite/setup_wizard.py`:

```python
def check_environment_parity() -> list[str]:
    """Validate local environment matches CI expectations."""
    issues = []
    
    # Check tool versions
    expected_ruff = "0.14"
    actual_ruff = _get_tool_version("ruff")
    if not actual_ruff.startswith(expected_ruff):
        issues.append(f"ruff version mismatch: expected {expected_ruff}, got {actual_ruff}")
    
    # Check lockfile sync
    result = subprocess.run(
        ["./scripts/refresh-deps.sh", "--check"],
        capture_output=True,
    )
    if result.returncode != 0:
        issues.append("Lockfiles out of sync with manifests")
    
    # Check Git hooks
    hooks_path = subprocess.run(
        ["git", "config", "core.hooksPath"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if hooks_path != ".githooks":
        issues.append("Git hooks not configured (run scripts/setup-dev-env.sh)")
    
    return issues
```

### 4. Create Pre-commit Hook

Create `.githooks/pre-commit`:

```bash
#!/usr/bin/env bash
# Pre-commit hook that runs critical checks

set -e

echo "Running pre-commit checks..."

# Check lockfile sync if dependency files changed
if git diff --cached --name-only | grep -qE "(pyproject.toml|package.json)"; then
  echo "Dependency files changed, checking lockfile sync..."
  ./scripts/refresh-deps.sh --check || {
    echo "❌ Lockfiles out of sync. Run: ./scripts/refresh-deps.sh"
    exit 1
  }
fi

# Quick format check (fast fail)
if ! ruff format --check --quiet; then
  echo "❌ Code not formatted. Run: ruff format"
  exit 1
fi

echo "✓ Pre-commit checks passed"
```

### 5. Documentation

Add to CONTRIBUTING.md:

```markdown
## Development Environment Setup

1. **Clone and install dependencies**:
   ```bash
   git clone https://github.com/IAmJonoBo/IssueSuite.git
   cd IssueSuite
   pip install -e .[dev,all]
   ```

2. **Configure development environment**:
   ```bash
   ./scripts/setup-dev-env.sh
   ```
   
   This script:
   - Installs Git pre-commit hooks
   - Validates lockfile synchronization
   - Checks tool version parity with CI

3. **Verify setup**:
   ```bash
   issuesuite doctor  # Validates environment
   nox -s tests lint typecheck  # Runs quality gates locally
   ```

4. **Before committing**:
   - Pre-commit hooks automatically run format checks and lockfile validation
   - Run `nox -s lint typecheck` to catch issues early
   - Update lockfiles after dependency changes: `./scripts/refresh-deps.sh`

## Tool Versions

Local development should use the same tool versions as CI:
- **Python**: 3.10+ (CI tests 3.10, 3.11, 3.12, 3.13)
- **ruff**: 0.14 (pinned exact version)
- **mypy**: 1.8+
- **Node.js**: 20+ (for documentation)

These are automatically installed when you run `pip install -e .[dev]`.
```

## Consequences

### Positive

- **Eliminates "works on my machine" failures** related to tool version mismatches
- **Faster feedback loop** — Developers catch issues before pushing to CI
- **Consistent code quality** — Same linting rules enforced everywhere
- **Better onboarding** — Clear setup process for new contributors
- **Reduced CI costs** — Fewer failed builds from preventable issues
- **Git hook automation** — Pre-commit checks catch common mistakes

### Negative

- **Setup overhead** — Contributors must run setup script (one-time cost)
- **Hook maintenance** — Git hooks need updates when checks change
- **Strictness trade-off** — Some developers may prefer looser local workflows
- **Tool dependency** — Requires `nox`, `uv`, and other tools locally

### Neutral

- **Optional enforcement** — Pre-commit hooks can be bypassed with `--no-verify` if needed for emergency fixes
- **Gradual adoption** — Existing contributors can adopt incrementally
- **CI remains source of truth** — Local checks are helpers, not replacements for CI

## Alternatives Considered

### 1. Dev containers / Codespaces

**Considered**: Would provide perfect parity but high complexity. May adopt in future.

**Pros**: Complete environment reproducibility, no local tool installation  
**Cons**: Requires Docker, slower iteration, complex setup

**Decision**: Document as future enhancement, focus on lightweight approach first

### 2. Strict pre-commit hooks (cannot bypass)

**Rejected**: Too restrictive. Developers sometimes need to commit WIP for collaboration.

### 3. Automated tool version updates

**Rejected**: Tools should be updated deliberately with testing, not automatically.

### 4. No enforcement, just documentation

**Rejected**: Documentation alone is insufficient. Automated checks provide better guarantees.

## Follow-up Tasks

- [ ] Create `scripts/setup-dev-env.sh`
- [ ] Enhance `issuesuite doctor` with parity checks
- [ ] Add pre-commit hook to `.githooks/pre-commit`
- [ ] Update CONTRIBUTING.md with setup guide
- [ ] Add "Dev Environment Setup" to README.md
- [ ] Consider Dev Containers as future enhancement
- [ ] Add environment validation to release checklist

## Related ADRs

- ADR-0002: Automated Dependency Synchronization Enforcement
- ADR-0003: Hermetic Packaging Validation

## References

- **Gap Analysis 2025**: docs/gap_analysis_2025.md — Identifies environment parity as high-priority gap
- **Quality Gates**: scripts/quality_gates.py — Tools that must match between local and CI
- **Setup Wizard**: src/issuesuite/setup_wizard.py — Existing environment validation foundation
- **Nox Sessions**: noxfile.py — Local quality gate execution
