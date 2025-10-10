# Release Checklist

This checklist ensures all quality gates, validations, and documentation updates are complete before releasing a new version of IssueSuite.

## Pre-Release Validation

### Environment Parity (ADR-0004)
- [ ] Run `./scripts/setup-dev-env.sh` to validate development environment
- [ ] Verify Git hooks are configured: `git config core.hooksPath` returns `.githooks`
- [ ] Run `issuesuite doctor` to check environment health
- [ ] Confirm all development tools match CI versions (see `pyproject.toml` dev dependencies)

### Dependency Synchronization (ADR-0002)
- [ ] Verify lockfiles are synchronized: `./scripts/refresh-deps.sh --check`
- [ ] Ensure no drift in `uv.lock` or `docs/starlight/package-lock.json`
- [ ] Review Renovate PRs for any pending dependency updates
- [ ] Confirm CI `dependencies.yml` workflow is passing

### Hermetic/Offline Validation (ADR-0003)
- [ ] Run offline installation tests: `nox -s test_hermetic`
- [ ] Verify core functionality works with `ISSUES_SUITE_MOCK=1`
- [ ] Test optional dependency graceful degradation
- [ ] Confirm `sitecustomize.py` handles missing pip-audit gracefully
- [ ] Validate that all CI hermetic tests pass

### Quality Gates
- [ ] Run full test suite: `nox -s tests`
- [ ] Run linters: `nox -s lint`
- [ ] Run type checking: `nox -s typecheck`
- [ ] Run security scanning: `nox -s security`
- [ ] Run secret detection: `nox -s secrets`
- [ ] Verify coverage meets threshold (≥80%)

### Documentation
- [ ] Update CHANGELOG.md with release notes
- [ ] Verify README.md is current and accurate
- [ ] Ensure CONTRIBUTING.md reflects latest workflows
- [ ] Check that all ADRs are up-to-date
- [ ] Build documentation: `nox -s docs`
- [ ] Review documentation for broken links or outdated information

### Build Validation
- [ ] Build package: `python -m build`
- [ ] Verify wheel installs correctly: `pip install dist/*.whl`
- [ ] Test CLI in fresh environment: `issuesuite --help`
- [ ] Validate offline installation workflow (see ADR-0003)

## Release Process

### Version Bump
- [ ] Determine version number (semantic versioning: major.minor.patch)
- [ ] Run release script: `python scripts/release.py <version> --dry-run`
- [ ] Review proposed changes
- [ ] Execute release: `python scripts/release.py <version> --push`

### CI/CD
- [ ] Verify all CI workflows pass on release tag
- [ ] Monitor `publish.yml` workflow for PyPI upload
- [ ] Confirm package appears on PyPI: https://pypi.org/project/issuesuite/
- [ ] Test installation from PyPI: `pipx install issuesuite`

### Post-Release
- [ ] Create GitHub release with notes
- [ ] Update documentation site (if applicable)
- [ ] Announce release (if applicable)
- [ ] Close milestone in GitHub Issues (if applicable)

## Continuous Improvements

### Success Metrics (ADR-0002)
- Zero lockfile drift incidents in merged PRs
- Zero "works on my machine" dependency-related failures
- 100% of CI runs with synchronized lockfiles

### Security Posture
- Advisory refresh runs automatically
- No stale security advisories (≤24h)
- SBOM generation successful in publish workflow

### Developer Experience
- All contributors follow documented workflows
- Pre-commit hooks catch common issues
- Quality gates provide clear feedback

## References

- **ADR-0002**: Automated Dependency Synchronization Enforcement
- **ADR-0003**: Hermetic Packaging Validation
- **ADR-0004**: Development Environment Parity
- **Gap Analysis**: docs/gap_analysis_2025.md
- **Release Script**: scripts/release.py
