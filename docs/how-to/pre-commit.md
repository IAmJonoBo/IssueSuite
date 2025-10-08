# Integrate IssueSuite with pre-commit

Add a local hook to guard against malformed specs before they reach CI:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: issuesuite-validate
        name: IssueSuite Validate
        entry: issuesuite
        language: system
        pass_filenames: false
        args: ["validate", "--config", "issue_suite.config.yaml"]
```

Recommendations:

- Set `ISSUES_SUITE_MOCK=1` in the hook environment to avoid network calls during validation.
- Add a pre-push hook that runs `scripts/issuesuite-preflight.sh` for teams that want automated dry-run gating.
- Share the generated `issues_summary.json` and `issues_plan.json` artifacts with pull request bots for visibility.
