# Next Steps Tracker

| Priority | Status      | Area         | Summary                                           | Notes                                                                                                                                               |
| -------- | ----------- | ------------ | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| High     | In Progress | Lint & Types | Add missing type annotations across scripts/tests | Continue annotating tests flagged by `ruff --select ANN`; unblock `mypy` expansion later. ✅ `tests/test_env_auth.py` fully annotated (2025-10-08). |
| High     | Not Started | Lint         | Tackle remaining lint blockers                    | Address import ordering, redundant casts, markdown lint, and any new Ruff findings.                                                                 |
| High     | Not Started | Governance   | Blueprint Frontier Apex gates + GitHub Projects automation | Expand coverage target to ≥85, codify UX acceptance scripts, and sync Next Steps with Projects dashboards for executive reporting.                          |
| High     | Completed   | Supply Chain | Re-pin `.github/workflows/publish.yml` actions    | Restored `pypa/gh-action-pypi-publish` to commit `e53eb8b` and enabled Renovate digest pinning for the GitHub Actions manager.                      |
| High     | Completed   | Security     | Replace placeholder JWT signing                   | `_generate_jwt` now signs with PyJWT when available and falls back to a logged placeholder only if the dependency is absent.                        |
| High     | Completed   | Security     | Harden token caching                              | GitHub App tokens persist to the OS keyring (with encoded file backup) and legacy plaintext cache files are still readable for upgrades.            |
| High     | Completed   | Governance   | Frontier Elite quality gates (coverage ≥80, format, compile, governance validator) | `python scripts/quality_gates.py` + `python scripts/verify_next_steps.py` keep UX + GitHub Projects guardrails enforced in CI.【F:scripts/quality_gates.py†L21-L82】【F:scripts/verify_next_steps.py†L1-L33】 |
| Medium   | New         | Security UX  | Mask VS Code secret harvesting output             | `get_vscode_secrets` returns raw tokens; ensure callers redact or gate behind explicit opt-in to avoid accidental logging.                          |
| Medium   | Completed   | Typing       | Ship `py.typed` marker                            | Added `src/issuesuite/py.typed` and updated `MANIFEST.in` to ensure type hints ship with the wheel.                                                 |
| Medium   | Completed   | Supply Chain | Pin build tooling in workflows                    | Workflow now installs `pip==24.2`, `build==1.2.2.post1`, and `twine==6.2.0`; evaluate adding `--require-hashes` once digests are curated.           |
| Medium   | New         | Testing      | Add security regression tests                     | Add unit/integration coverage for GitHub App auth failures, JWT validation, and token cache permissions.                                            |
| Medium   | New         | Tooling      | Stabilise pip-audit in offline CI                 | Investigate resilient timeouts/offline datasets so `pip-audit --strict` no longer hangs without network access.                                     |

## Notes

- Renovate is now configured to pin GitHub Actions digests. Consider adding a CI status check to ensure Renovate PRs for action updates are reviewed promptly.
- PyJWT and keyring are now optional auth dependencies; ensure production environments install the `all` extra (or a dedicated `auth` extra) so GitHub App sync remains functional.
- `pip-audit --strict` currently stalls in sandboxed containers; wire resilient timeout/offline dataset handling before promoting the gate to required status.
- Frontier Apex planning should involve PMO + UX leads; capture accessibility heuristics and Projects automation requirements alongside engineering tasks.
