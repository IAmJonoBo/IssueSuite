---
id: ADR-0003
title: Hermetic Packaging Validation
status: Accepted
decision_date: 2025-10-09
authors:
  - IssueSuite Maintainers
tags:
  - packaging
  - ci
  - security
  - offline
---

## Context

IssueSuite is designed to work in various deployment environments, including:
- Air-gapped/hermetic CI runners without external network access
- Enterprise environments with restrictive firewalls
- Ephemeral runners that may have inconsistent tool availability
- Development machines with varying levels of internet connectivity

The package includes optional dependencies (`[all]`, `[dev]`, `[observability]`, etc.) that enhance functionality but should gracefully degrade when unavailable. Several modules already implement fallback behavior (e.g., `pip_audit_integration.py`, `observability.py`), but there's no automated validation that:

1. The package installs successfully in offline environments
2. Optional dependencies degrade gracefully rather than causing hard failures
3. Core functionality works without network access

**Current Gap**: The `test-build.yml` workflow validates wheel installation and basic CLI invocation, but only in online environments with full network access. This means offline deployment failures might not be discovered until production.

## Decision

We will validate hermetic packaging through automated CI tests that simulate offline/restricted environments:

1. **Offline installation tests** — Validate the wheel installs without network access using only the built distribution and its required dependencies.

2. **Graceful degradation tests** — Verify optional dependencies can be omitted without breaking core functionality.

3. **Ephemeral runner simulation** — Test scenarios where common tools (`uv`, `npm`, `git`) may not be available.

4. **Mock mode validation** — Ensure `ISSUES_SUITE_MOCK=1` works completely offline for testing.

5. **Network-isolated CI job** — Add a CI job that runs with network disabled to catch regressions.

## Implementation

### Enhanced test-build.yml Workflow

Add a new job to `.github/workflows/test-build.yml`:

```yaml
  offline-installation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Build package
        run: |
          python -m pip install --upgrade pip build
          python -m build
      
      - name: Create offline environment
        run: |
          # Download all required dependencies to a local directory
          mkdir -p /tmp/offline-wheels
          pip download --dest /tmp/offline-wheels dist/*.whl
      
      - name: Test offline installation
        run: |
          # Create fresh venv and install without network
          python -m venv /tmp/offline-venv
          /tmp/offline-venv/bin/pip install \
            --no-index \
            --find-links /tmp/offline-wheels \
            issuesuite
      
      - name: Test core functionality offline
        run: |
          # Verify basic CLI works in offline mode
          /tmp/offline-venv/bin/python -m issuesuite --help
          /tmp/offline-venv/bin/python -m issuesuite schema
        env:
          ISSUES_SUITE_MOCK: "1"
          ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE: "1"
      
      - name: Test without optional dependencies
        run: |
          # Install only core dependencies
          python -m venv /tmp/minimal-venv
          /tmp/minimal-venv/bin/pip install dist/*.whl
          
          # Verify degradation is graceful
          /tmp/minimal-venv/bin/python -c "
          import issuesuite
          # Should work without opentelemetry, psutil, etc.
          print('Core import successful')
          "
```

### Regression Tests

Create `tests/test_hermetic_installation.py` to validate offline behavior:

```python
"""Test hermetic/offline installation scenarios."""

import subprocess
import sys
from pathlib import Path

def test_core_imports_without_optional_deps(monkeypatch):
    """Verify core functionality works without optional dependencies."""
    # Simulate missing optional dependencies
    monkeypatch.setattr("sys.modules", {
        **sys.modules,
        "opentelemetry": None,
        "psutil": None,
        "keyring": None,
    })
    
    # Core imports should still work
    from issuesuite import load_config, IssueSuite
    assert load_config is not None
    assert IssueSuite is not None

def test_cli_works_in_mock_mode_offline(tmp_path):
    """Verify CLI functions in offline mock mode."""
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\nsource:\n  file: ISSUES.md\n")
    
    issues = tmp_path / "ISSUES.md"
    issues.write_text("# Issues\n\n## [slug: test]\n\n```yaml\ntitle: Test\n```\n")
    
    # Should work without network
    result = subprocess.run(
        [sys.executable, "-m", "issuesuite", "validate", "--config", str(config)],
        env={**os.environ, "ISSUES_SUITE_MOCK": "1"},
        capture_output=True,
    )
    assert result.returncode == 0
```

### Documentation Updates

Add to README.md:

```markdown
## Offline/Hermetic Deployment

IssueSuite supports air-gapped and hermetic environments:

- **Core functionality** works without network access when `ISSUES_SUITE_MOCK=1` is set
- **Optional dependencies** gracefully degrade if unavailable
- **Offline testing** is validated in CI via hermetic installation tests

For offline deployment:
1. Build the wheel: `python -m build`
2. Transfer `dist/*.whl` to target environment
3. Install: `pip install --no-index --find-links ./dist issuesuite`
4. Use mock mode: `export ISSUES_SUITE_MOCK=1`
```

## Consequences

### Positive

- **Increased deployment flexibility**: Package works in air-gapped environments
- **Better error handling**: Optional dependencies fail gracefully
- **Regression prevention**: CI catches offline deployment issues before release
- **Security**: Reduces external network dependencies in production
- **Confidence**: Validated that core functionality doesn't require external services

### Negative

- **CI complexity**: Adds another job to test-build workflow (~2 minutes)
- **Test maintenance**: Hermetic tests require more setup/teardown
- **Coverage trade-offs**: Network-disabled tests can't validate online features

### Neutral

- **Optional features still optional**: Observability, keyring, etc. remain opt-in
- **No changes to core architecture**: Existing fallback patterns are sufficient
- **Documentation requirements**: Need clear guidance on offline deployment

## Alternatives Considered

### 1. Vendor all dependencies

**Rejected**: Would bloat the repository and create maintenance burden. Better to validate graceful degradation.

### 2. Require all optional dependencies

**Rejected**: Defeats the purpose of optional dependencies and increases deployment friction.

### 3. Document offline support without testing

**Rejected**: Untested guarantees are not guarantees. CI validation provides confidence.

### 4. Use Docker for hermetic testing

**Considered**: Could provide better isolation but adds complexity. File-based approach is simpler for now. May revisit for future enhancements.

## Follow-up Tasks

- [x] Add `offline-installation` job to `.github/workflows/test-build.yml`
- [x] Create `tests/test_hermetic_installation.py` with regression tests
- [x] Update README.md with offline deployment guide
- [x] Document mock mode environment variables in reference docs (see docs/reference/environment-variables.mdx)
- [x] Add offline validation to release checklist (see docs/RELEASE_CHECKLIST.md)
- [ ] Consider Docker-based hermetic testing for future enhancement

## Related ADRs

- ADR-0002: Automated Dependency Synchronization Enforcement
- ADR-0004: Development Environment Parity (proposed)

## References

- **Gap Analysis 2025**: docs/gap_analysis_2025.md — Identifies hermetic packaging as high-priority gap
- **Pip Audit Integration**: src/issuesuite/pip_audit_integration.py — Example of graceful degradation
- **Observability Module**: src/issuesuite/observability.py — Optional dependency handling pattern
- **Test Build Workflow**: .github/workflows/test-build.yml — Current packaging validation
