# Packaging and Distribution Guide

## Building the Package

Build the package locally:
```bash
pip install build
python -m build
```

This creates both wheel (`.whl`) and source distribution (`.tar.gz`) in the `dist/` directory.

## Testing the Package

Test the built package:
```bash
# Check package metadata and structure
twine check dist/*

# Install and test locally
pip install dist/issuesuite-*.whl
issuesuite --help

# Test with pipx
pipx install dist/issuesuite-*.whl
```

## Publishing to PyPI

### Setup (one-time)
1. Configure PyPI trusted publishing in your repository settings
2. Add the `pypi` environment to your GitHub repository

### Release Process
1. Update version in `pyproject.toml` and `src/issuesuite/__init__.py`
2. Update `CHANGELOG.md` with new features/fixes
3. Create a git tag and GitHub release
4. The GitHub workflow will automatically publish to PyPI

### Manual Publishing
For testing or manual releases:
```bash
# Test PyPI (optional)
twine upload --repository testpypi dist/*

# Production PyPI
twine upload dist/*
```

## Installation Methods

Users can install IssueSuite in several ways:

```bash
# From PyPI (recommended)
pip install issuesuite

# With pipx (for CLI usage)
pipx install issuesuite

# From GitHub (latest)
pip install git+https://github.com/IAmJonoBo/IssueSuite.git

# From local build
pip install dist/issuesuite-*.whl
```

## Development Installation

For contributors:
```bash
# Run the setup script
python scripts/dev-setup.py

# Or manually
pip install -e .[dev,all]
```