## Summary

-
-

## Testing

- [ ] `pytest --cov=issuesuite --cov-report=term --cov-report=xml`
- [ ] `ruff check`
- [ ] `mypy src`
- [ ] `bandit -r src`
- [ ] `pip-audit --strict --progress-spinner off`
- [ ] `detect-secrets scan --baseline .secrets.baseline`
- [ ] `python -m build`

## Quality Gates

- [ ] Coverage ≥ 65%
- [ ] No lint/type/security findings
- [ ] Dependency audit clean
- [ ] Secrets baseline updated (if necessary)
- [ ] Build artifacts verified

## Risks & Rollback

- Risk level:
- Rollback plan:
