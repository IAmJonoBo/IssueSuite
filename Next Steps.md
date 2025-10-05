# Next Steps

## Tasks
- [x] **Owner:** Assistant (Due: TBD) — Ensure GitHub App JWT generation gracefully handles environments without the `gh` CLI so tests and real usage remain functional offline.
- [x] **Owner:** Assistant (Due: TBD) — Review and address Bandit low-severity findings (try/except patterns and subprocess usage) or document acceptances.
- [x] **Owner:** Assistant (Due: TBD) — Classify detect-secrets findings and determine if additional allowlists or remediation are required.

## Steps
- [x] Confirm baseline tooling by re-running pytest with coverage once GitHub App auth fallback is improved.
- [x] Re-run Bandit after documenting or resolving flagged patterns.
- [x] Re-run detect-secrets (or update baseline) after classification.

## Deliverables
- [x] Patched `src/issuesuite/github_auth.py` covering missing `gh` CLI scenarios and updated/added regression test(s).
- [x] Updated security scanning notes or suppressions where justified.
- [x] Baseline report summarizing tooling outcomes and remediation status.

## Quality Gates
- [x] Tests: `pytest --cov=issuesuite --cov-report=term-missing` — **passing** (coverage 69.10%).【693cea†L18-L36】
- [x] Lint: `ruff check` — **passing**.【52892b†L1-L2】
- [x] Type Check: `mypy src` — **passing**.【17be2c†L1-L2】
- [x] Security: `bandit -r src` — **passing**.【44d462†L1-L59】
- [x] Secrets: `detect-secrets scan` — **passing**.【dc3a10†L1-L69】
- [x] Build: `python -m build` — **passing**.【515787†L1-L86】

## Links
- [x] Failure log: tests/test_github_app_auth.py::test_jwt_generation_with_key_file — resolved by `pytest` chunk `022791†L1-L33`.
- [x] Security scan details — `bandit` chunk `44d462†L1-L59`.
- [x] Secrets scan summary — `detect-secrets` chunk `dc3a10†L1-L69`.
- [x] Quality gate roll-up — `python scripts/quality_gates.py` chunk `4063e3†L1-L6`.

## Risks / Notes
- [x] Missing GitHub CLI in CI-like environments prevented JWT generation; mitigated via CLI detection fallback (monitor logs for regressions).
- [x] Multiple Bandit findings stemmed from intentional subprocess usage; mitigated via command wrappers and inline documentation (monitor future changes).
- [x] Detect-secrets flags expected test fixtures; consider adding baseline or inline annotations without weakening coverage.
- [ ] Automate running `python scripts/quality_gates.py` in CI to prevent regressions.
