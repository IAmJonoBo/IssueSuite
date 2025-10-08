# CI/CD Automation Recipes

This guide shows how to integrate IssueSuite into automated pipelines for drift detection and safe apply runs.

## GitHub Actions: Dry-run gate

Start from the scaffolded workflow at `.github/workflows/issuesuite-sync.yml`. The job below validates specs, runs a dry-run sync, and uploads artifacts for review.

```yaml
jobs:
  dry-run-sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: |
          python -m pip install --upgrade pip
          pip install issuesuite
      - run: issuesuite validate --config issue_suite.config.yaml
      - run: |
          issuesuite sync --dry-run --update --config issue_suite.config.yaml \
            --summary-json issues_summary.json --plan-json issues_plan.json
      - uses: actions/upload-artifact@v4
        with:
          name: issuesuite-plan
          path: |
            issues_summary.json
            issues_plan.json
```

Tips:

- Set `ISSUESUITE_AI_MODE=1` to enforce dry-run mode in forks and pull requests.
- Add `plan-json` to capture mutation previews without writing local cache files.

## GitHub Actions: Apply pipeline

When the dry-run output is approved, trigger a second job that performs a write:

```yaml
jobs:
  apply-sync:
    needs: dry-run-sync
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install issuesuite
      - env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: issuesuite sync --update --config issue_suite.config.yaml \
          --summary-json issues_summary.json
```

Follow up with `issuesuite reconcile` in a gating workflow—exit code `2` indicates drift that needs attention.

## Publish releases and Homebrew taps

1. Tag a release using `scripts/release.py --patch` (or `--minor`/`--major`).
2. The `release.yml` workflow builds wheels, generates a Homebrew formula, checks metadata with `twine`, and publishes via PyPI Trusted Publishing.
3. Use `scripts/homebrew_formula.py` to sync the formula into your tap repository.

See [How-to: Homebrew tap automation](homebrew.md) for maintainer-focused steps and troubleshooting.
