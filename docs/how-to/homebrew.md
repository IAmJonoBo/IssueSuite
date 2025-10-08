# Homebrew Tap Automation

Use this guide when you want to distribute IssueSuite via a Homebrew tap.

## Generate the formula

The release workflow already runs the helper script:

```bash
python scripts/homebrew_formula.py \
  --dist-dir dist \
  --output packaging/homebrew/Formula/issuesuite.rb
```

You can regenerate locally after building the sdist (`python -m build`). Keep the generated formula committed so downstream taps stay in sync.

## Publish to your tap

1. Clone your tap repository (for example `github.com/your-org/homebrew-tap`).
2. Copy `packaging/homebrew/Formula/issuesuite.rb` into the tap's `Formula/` directory.
3. Commit with message `issuesuite <version>` and push.
4. Install with `brew tap your-org/tap` followed by `brew install your-org/tap/issuesuite`.

The template formula vendors PyYAML and installs IssueSuite via `virtualenv_install_with_resources`.
Update resource versions whenever dependencies change; the helper script currently pins PyYAML 6.0.2.

## Verify the formula locally

```bash
brew audit --new-formula --strict Formula/issuesuite.rb
brew install --build-from-source ./Formula/issuesuite.rb
brew test issuesuite
```

If the audit flags checksum mismatches, rebuild the distribution and regenerate the formula.
