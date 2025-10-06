# Packaging and Distribution Guide

This project publishes to PyPI using Trusted Publishers via GitHub Actions. Local packaging is optional for verification.

## Build locally (optional)

Use a virtual environment to keep your system Python clean:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install build twine
python -m build
```

This creates both wheel (.whl) and sdist (.tar.gz) under `dist/`.

To sanity-check the artifacts:

```bash
twine check dist/*
```

Optionally install locally:

```bash
pip install dist/issuesuite-*.whl
issuesuite --help
```

## Security audit

Run the hardened vulnerability scan locally before publishing:

```bash
issuesuite security --pip-audit --pip-audit-arg --format --pip-audit-arg json
```

This command prints the offline advisory table, writes JSON if requested, and forwards the remaining arguments to the resilient `pip-audit` wrapper so hermetic environments continue to receive actionable results.

Refresh the offline advisory dataset and assert freshness before packaging:

```bash
python -m issuesuite.advisory_refresh --refresh --check --max-age-days 30
```

This updates `src/issuesuite/data/security_advisories.json` from OSV metadata, merges curated overrides, and fails fast if the dataset is older than the permitted window.

## Publish to PyPI (Trusted Publishers)

We use PyPI Trusted Publishers; no API tokens are needed.

### One-time PyPI setup

1. On PyPI, open your project (issuesuite) → Manage → Trusted Publishers.
2. Add a GitHub Actions Trusted Publisher:
   - Owner: IAmJonoBo
   - Repository: IssueSuite
   - Workflow filename: .github/workflows/publish.yml
   - Environment: leave blank (recommended)
3. Save.

For TestPyPI, repeat the same at [test.pypi.org](https://test.pypi.org/) for the same repo/workflow.

### Release steps

1. Bump version in both `pyproject.toml` and `src/issuesuite/__init__.py`.
2. Update `CHANGELOG.md`.
3. Create a GitHub Release (or push a tag and then publish a release).
4. The “Publish to PyPI” workflow builds and uploads. Re-runs are safe due to `skip-existing: true`.

To publish to TestPyPI instead, dispatch the workflow with the `test_pypi` input set to true.

## Installation methods

```bash
# From PyPI (recommended)
pip install issuesuite

# With pipx (recommended for CLI)
pipx install issuesuite

# From GitHub (latest main)
pip install git+https://github.com/IAmJonoBo/IssueSuite.git

# From local build
pip install dist/issuesuite-*.whl
```

## Development install

For contributors working locally:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev,all]'
```
