# Contributing to IssueSuite

Thank you for contributing to IssueSuite! This guide will help you get set up and understand our development workflow.

## Quick Start

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
   - Provides environment diagnostics

3. **Verify setup**:
   ```bash
   issuesuite doctor  # Check environment health
   nox -s tests lint typecheck  # Run quality gates locally
   ```

## Development Workflow

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards below

3. **Run quality gates** before committing:
   ```bash
   nox -s tests lint typecheck  # Fast local validation
   nox -s security secrets  # Additional checks
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```
   
   Pre-commit hooks will automatically:
   - Check code formatting
   - Validate lockfile synchronization (if dependencies changed)

### Dependency Management

IssueSuite uses multiple dependency manifests:
- `pyproject.toml` — Python dependencies
- `uv.lock` — Reproducible Python environment
- `docs/starlight/package.json` — Documentation dependencies
- `docs/starlight/package-lock.json` — Reproducible Node.js environment

**When to update dependencies:**

1. **Adding a new dependency**:
   ```bash
   # Edit pyproject.toml to add dependency
   ./scripts/refresh-deps.sh  # Update lockfiles
   git add pyproject.toml uv.lock
   git commit -m "Add new dependency: package-name"
   ```

2. **Updating existing dependencies**:
   ```bash
   # Edit pyproject.toml with new version constraint
   ./scripts/refresh-deps.sh  # Update lockfiles
   git add pyproject.toml uv.lock
   git commit -m "Update dependency: package-name"
   ```

3. **Updating documentation dependencies**:
   ```bash
   cd docs/starlight
   # Edit package.json
   npm install --package-lock-only
   cd ../..
   ./scripts/refresh-deps.sh  # Sync both lockfiles
   git add docs/starlight/package.json docs/starlight/package-lock.json
   git commit -m "Update docs dependency: package-name"
   ```

**Important**: Always run `./scripts/refresh-deps.sh` after modifying dependency manifests. The CI pipeline will reject PRs with out-of-sync lockfiles.

### Coding Standards

- **Formatting**: Use `ruff format` (enforced by pre-commit hooks)
- **Linting**: Use `ruff check` (must pass in CI)
- **Type checking**: Use `mypy src` (must pass in CI)
- **Line length**: 100 characters maximum
- **Testing**: Write tests for new features in `tests/`

### Testing

**Run tests locally**:
```bash
# All tests with coverage
nox -s tests

# Specific test file
pytest tests/test_your_feature.py -v

# Fast mock-mode tests
ISSUES_SUITE_MOCK=1 pytest
```

**Test coverage requirements**:
- Overall coverage: ≥80%
- New code: Aim for ≥85% coverage
- Critical paths: 100% coverage expected

**Writing tests**:
- Use fixtures from `conftest.py`
- Use `ISSUES_SUITE_MOCK=1` for offline tests
- Follow existing test patterns in `tests/`

### Documentation

**Build documentation locally**:
```bash
nox -s docs  # Build and check documentation
cd docs/starlight && npm run dev  # Live preview
```

**Documentation structure** (Diátaxis framework):
- `docs/starlight/src/content/docs/tutorials/` — Learning-oriented
- `docs/starlight/src/content/docs/how-to/` — Problem-oriented
- `docs/starlight/src/content/docs/reference/` — Information-oriented
- `docs/starlight/src/content/docs/explanations/` — Understanding-oriented

### Architecture Decision Records (ADRs)

For significant architectural changes:

1. **Create new ADR**:
   ```bash
   cp docs/adrs/ADR-0001-starlight-migration.md docs/adrs/ADR-NNNN-your-decision.md
   # Edit with your decision context and consequences
   ```

2. **Update ADR index**:
   Edit `docs/adrs/index.json` to include your new ADR

3. **Link from implementation**:
   Reference the ADR in code comments or commit messages

See `docs/starlight/src/content/docs/how-to/adr-governance.mdx` for full workflow.

## Offline/Hermetic Development

IssueSuite supports air-gapped development:

**Offline mode**:
```bash
export ISSUES_SUITE_MOCK=1  # Disable GitHub API calls
export ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE=1  # Disable pip-audit network requests
```

**Offline package installation**:
```bash
# Build wheel
python -m build

# Download dependencies
mkdir -p offline-wheels
pip download --dest offline-wheels dist/*.whl

# Install offline
pip install --no-index --find-links offline-wheels issuesuite
```

## Pull Request Process

1. **Ensure all tests pass locally**:
   ```bash
   nox -s tests lint typecheck security secrets
   ```

2. **Update documentation** if you changed:
   - CLI commands or flags
   - Configuration format
   - Public APIs

3. **Add changelog entry** (optional for minor changes):
   Edit `CHANGELOG.md` under "Unreleased" section

4. **Submit PR** with:
   - Clear description of changes
   - Reference to related issues
   - Test coverage for new features

5. **CI checks** will validate:
   - Tests pass on Python 3.10, 3.11, 3.12, 3.13
   - Lockfiles are synchronized
   - Code passes quality gates
   - Documentation builds successfully
   - Package builds and installs correctly

6. **Address review feedback** and update PR

## Tool Versions

Match CI environment for consistency:
- **Python**: 3.10+ (CI tests 3.10, 3.11, 3.12, 3.13)
- **ruff**: 0.14 (pinned exact version)
- **mypy**: 1.8+
- **Node.js**: 20+ (for documentation)
- **uv**: Latest (for lockfile management)

Install via:
```bash
pip install -e .[dev,all]  # Python tools
npm install  # Node.js tools (in docs/starlight/)
pip install uv  # Lockfile manager
```

## Environment Variables

**Development**:
- `ISSUES_SUITE_MOCK=1` — Mock GitHub API calls
- `ISSUESUITE_DEBUG=1` — Verbose logging
- `ISSUESUITE_QUIET=1` — Suppress logs

**Testing**:
- `ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE=1` — Offline pip-audit
- `ISSUESUITE_PROJECT_CACHE_DISABLE=1` — Disable project cache

**CI/Production**:
- `ISSUESUITE_AI_MODE=1` — Force dry-run mode for AI agents
- `ISSUESUITE_RETRY_ATTEMPTS=N` — Retry attempts (default: 3)

## Troubleshooting

### Lockfiles out of sync
```bash
./scripts/refresh-deps.sh  # Fix lockfiles
git add uv.lock docs/starlight/package-lock.json
```

### Pre-commit hooks failing
```bash
ruff format  # Auto-fix formatting
./scripts/refresh-deps.sh  # Fix lockfiles
git add -u && git commit
```

### Tests failing locally but passing in CI
```bash
# Ensure tools match CI versions
pip install -e .[dev,all] --force-reinstall

# Check environment
issuesuite doctor
```

### Documentation build fails
```bash
cd docs/starlight
npm install  # Ensure dependencies are current
npm run check  # Validate content
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/IAmJonoBo/IssueSuite/issues)
- **Discussions**: [GitHub Discussions](https://github.com/IAmJonoBo/IssueSuite/discussions)
- **Documentation**: [IssueSuite Docs](https://github.com/IAmJonoBo/IssueSuite#readme)

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to make IssueSuite better.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
