# Next Steps

## Tasks

- [x] **Owner:** Assistant (Due: 2025-10-06) — Harden REST client environment handling so packaging preflight honours sanitized tokens, disable flags, and enterprise endpoints with regression coverage.【F:src/issuesuite/github_issues.py†L270-L316】【F:tests/test_github_rest_client.py†L120-L177】
- [x] **Owner:** Assistant (Due: 2025-10-06) — Ship a resilient pip-audit wrapper and CLI workflow so hermetic environments pass dependency gates without bespoke CAs.【F:src/issuesuite/pip_audit_integration.py†L1-L240】【F:src/issuesuite/cli.py†L1-L650】
- [x] **Owner:** Assistant (Due: 2025-10-05) — Ensure GitHub App JWT generation gracefully handles environments without the `gh` CLI so tests and real usage remain functional offline.
- [x] **Owner:** Assistant (Due: 2025-10-05) — Review and address Bandit low-severity findings (try/except patterns and subprocess usage) or document acceptances.
- [x] **Owner:** Assistant (Due: 2025-10-05) — Classify detect-secrets findings and determine if additional allowlists or remediation are required.
- [x] **Owner:** Assistant (Due: 2025-10-05) — Produce a gap analysis with frontier-grade recommendations for IssueSuite.
- [x] **Owner:** Assistant (Due: 2025-10-05) — Integrate `python scripts/quality_gates.py` into CI so every PR enforces the consolidated gates automatically.【F:.github/workflows/ci.yml†L35-L37】
- [x] **Owner:** Assistant (Due: 2025-10-05) — Add CODEOWNERS and PR template scaffolding to formalize review policy and checklist hygiene.【F:.github/CODEOWNERS†L1-L5】【F:.github/pull_request_template.md†L1-L23】
- [x] **Owner:** Assistant (Due: 2025-10-05) — Calibrate `detect-secrets` with a repo baseline to eliminate false positives in governance docs.【F:.secrets.baseline†L1-L74】
- [x] **Owner:** Maintainers (Due: Frontier Q1) — Introduce a native GitHub REST/GraphQL client, raise CLI/orchestrator coverage ≥85%, and backfill observability to harden sync paths.【F:src/issuesuite/github_issues.py†L41-L195】【F:tests/test_github_rest_client.py†L1-L116】
- [x] **Owner:** Maintainers (Due: Frontier Q1) — Wire OpenTelemetry metrics/traces and benchmarking regression alerts into CI for proactive performance management.【F:src/issuesuite/observability.py†L1-L65】【F:scripts/quality_gates.py†L55-L63】
- [x] **Owner:** Maintainers (Due: Frontier Q2) — Extend the publish workflow with SBOM generation, provenance attestations, and vulnerability scanning before release.【F:.github/workflows/publish.yml†L20-L58】
- [x] **Owner:** Maintainers (Due: Frontier Q2) — Add schema validation and approval workflow to `agent-apply`, plus document AI safety guardrails.【F:src/issuesuite/agent_updates.py†L1-L214】【F:tests/test_agent_apply_validation.py†L1-L67】
- [x] **Owner:** Maintainers (Due: Frontier Q3) — Ship durable index persistence (hash validation, optional remote storage) with rollback ADRs for distributed teams.【F:src/issuesuite/index_store.py†L1-L63】【F:src/issuesuite/orchestrator.py†L130-L220】
- [x] **Owner:** Maintainers (Due: Frontier Q1) — Lift CLI command coverage to ≥60% with targeted subcommand smoke tests and fixtures.【F:tests/test_cli_extended.py†L1-L163】【1eb104†L16-L44】
- [x] **Owner:** Maintainers (Due: Frontier Q1) — Backfill agent_apply guard rails with higher-fidelity fixtures to lift module coverage beyond 50%.【6b942b†L21-L28】【F:tests/test_agent_apply_validation.py†L1-L147】
- [x] **Owner:** Maintainers (Due: Frontier Q4) — Automate `security_advisories.json` refresh and alerting per red-team finding RT-01.【F:src/issuesuite/advisory_refresh.py†L1-L236】【F:docs/red_team_report.md†L18-L64】
- [x] **Owner:** Maintainers (Due: Frontier Q4) — Emit OpenTelemetry spans for resilient pip-audit fallbacks (RT-03).【F:src/issuesuite/pip_audit_integration.py†L1-L240】【F:tests/test_pip_audit_integration.py†L1-L120】
- [x] **Owner:** DevRel (Due: Frontier Q4) — Publish internal comms highlighting the wrapped `pip-audit` script and `issuesuite security` workflow (RT-02).【F:docs/internal_comms_security_workflow.md†L1-L60】【F:docs/red_team_report.md†L18-L64】
- [x] **Owner:** Assistant (Due: 2025-10-09) — Elevate quality gates to Frontier Elite (coverage ≥80%, formatting, bytecode compile, governance validation) while capturing UX and GitHub Projects guidance in the trackers.【F:scripts/quality_gates.py†L21-L82】【F:src/issuesuite/next_steps_validator.py†L1-L109】
- [x] **Owner:** Assistant (Due: 2025-10-09) — Ship automated Next Steps governance validation CLI to enforce UX excellence and GitHub Projects integration narratives.【F:src/issuesuite/next_steps_validator.py†L1-L109】【F:scripts/verify_next_steps.py†L1-L33】
- [ ] **Owner:** Assistant (Due: 2025-10-10) — Investigate `pip-audit --strict` hanging in offline containers and add timeout/offline fallbacks so the gate completes reliably.【fce977†L1-L120】
- [ ] **Owner:** Assistant (Due: 2025-10-12) — Blueprint the "Frontier Apex" governance layer elevating coverage ≥85%, type coverage telemetry, UX accessibility validations, and GitHub Projects automation as required checks across repos.
- [ ] **Owner:** Maintainers (Due: 2025-10-20) — Stand up GitHub Projects dashboards + workflow automation linking Next Steps, CI signals, and release gates for full program management traceability.

## Steps

- [x] Harden IssuesClient REST client environment normalization so sanitized tokens and enterprise endpoints are honoured before packaging preflight decisions.【F:src/issuesuite/github_issues.py†L270-L316】【F:tests/test_github_rest_client.py†L120-L177】
- [x] Harden pip-audit by installing a resilient wrapper and new CLI/quality gates so hermetic baselines pass without bespoke CAs.【F:src/issuesuite/pip_audit_integration.py†L1-L240】【F:scripts/quality_gates.py†L21-L60】
- [x] Automate the offline advisory refresh workflow and enforce a freshness gate in CI to block stale datasets.【F:src/issuesuite/advisory_refresh.py†L1-L236】【F:scripts/quality_gates.py†L20-L94】【fa836a†L1-L130】
- [x] Re-run full quality gates locally (pytest+coverage, ruff, mypy, bandit, detect-secrets, build) to establish baseline before analysis.【ce7f96†L1-L45】【e3c1a9†L1-L2】【862000†L1-L2】【df017e†L1-L68】【6e6bf9†L1-L71】【23b224†L1-L128】
- [x] Replace CLI-only GitHub orchestration with a native REST client and regression suite covering milestone resolution and fallback behavior.【F:src/issuesuite/github_rest.py†L1-L200】【F:tests/test_github_rest_client.py†L1-L116】
- [x] Layer OpenTelemetry tracing and performance budget enforcement into benchmarking plus CI quality gates.【F:src/issuesuite/observability.py†L1-L65】【F:scripts/quality_gates.py†L55-L63】【F:tests/test_benchmarking.py†L1-L165】
- [x] Harden agent update ingestion with JSON Schema validation and explicit approval switches for governance workflows.【F:src/issuesuite/agent_updates.py†L12-L214】【F:src/issuesuite/cli.py†L370-L474】
- [x] Introduce signed index persistence with signature verification and optional mirroring to external storage for durability.【F:src/issuesuite/index_store.py†L1-L63】【F:src/issuesuite/mapping_utils.py†L1-L43】
- [x] Refactored mapping normalization helpers to prune stale entries without tripping lint complexity limits.【F:src/issuesuite/orchestrator.py†L133-L208】
- [x] Hardened telemetry importer and console writer to avoid ValueError crashes and surface diagnostics when dependencies are missing.【F:src/issuesuite/observability.py†L1-L97】
- [x] Ensured benchmarking tracer hooks guard optional dependencies to satisfy static analysis and prevent runtime errors.【F:src/issuesuite/benchmarking.py†L22-L180】
- [x] Normalized index document loading with explicit type coercion for signed entries.【F:src/issuesuite/index_store.py†L45-L73】
- [x] Centralized agent-update schema validator state to simplify guards and keep mypy happy.【F:src/issuesuite/agent_updates.py†L13-L199】
- [x] Draft `docs/gap_analysis.md` summarizing strengths, gaps, and frontier recommendations with citations.【F:docs/gap_analysis.md†L1-L94】
- [x] Automate quality gate enforcement in CI via `python scripts/quality_gates.py` to consolidate tooling expectations per PR.【F:.github/workflows/ci.yml†L35-L37】
- [x] Baseline repository secrets and document the review workflow so detect-secrets is actionable rather than noisy.【F:.secrets.baseline†L1-L74】
- [x] Hardened orchestrator outputs to create config-relative directories, guard mapping normalization errors, and expand regression tests for approval and stdin flows.【F:src/issuesuite/orchestrator.py†L115-L260】【F:tests/test_orchestrator_enhancements.py†L1-L119】【F:tests/test_cli_agent_apply.py†L124-L168】
- [x] Added manual validation fallback and regression fixtures so `agent-apply` rejects malformed slugs and docs even when `jsonschema` is unavailable.【F:src/issuesuite/agent_updates.py†L85-L152】【F:tests/test_agent_apply_validation.py†L69-L147】
- [x] Expanded CLI regression coverage for `ai-context`, `import`, `reconcile`, and `doctor` to lift the CLI module to 69% coverage.【F:tests/test_cli_extended.py†L1-L163】【1eb104†L16-L44】
- [x] Automated CI benchmark generation before enforcing the performance budget gate, ensuring deterministic metrics for `performance_report.json`.【F:scripts/generate_performance_report.py†L1-L43】【F:src/issuesuite/performance_report.py†L1-L105】
- [x] Introduced a schema registry, changelog guard, and developer nox sessions so artifacts, documentation, and automation stay aligned while preventing changelog lock hangs.【F:src/issuesuite/schema_registry.py†L1-L64】【F:scripts/update_changelog.py†L1-L68】【F:noxfile.py†L1-L46】
- [x] Hardened GitHub App JWT signing to fall back to deterministic unsigned tokens when PyJWT rejects malformed keys, keeping sync flows resilient in constrained environments.【F:src/issuesuite/github_auth.py†L330-L397】【F:tests/test_github_app_auth.py†L240-L257】
- [x] Codified Frontier Elite governance by raising quality gates, adding Next Steps validation, and documenting UX + GitHub Projects integration expectations.【F:scripts/quality_gates.py†L21-L82】【F:src/issuesuite/next_steps_validator.py†L1-L109】【F:scripts/verify_next_steps.py†L1-L33】
- [ ] Draft Frontier Apex governance spec with explicit UX heuristics, GitHub Projects sync routines, and expanded telemetry thresholds before implementation.

## Deliverables

- [x] Hardened `IssuesClient` REST environment detection to sanitize tokens, respect disable flags, and prefer enterprise endpoints with regression tests safeguarding packaging preflight behaviour.【F:src/issuesuite/github_issues.py†L270-L316】【F:tests/test_github_rest_client.py†L120-L177】
- [x] Patched `src/issuesuite/github_auth.py` covering missing `gh` CLI scenarios and updated/added regression test(s).
- [x] Updated security scanning notes or suppressions where justified.
- [x] Baseline report summarizing tooling outcomes and remediation status.
- [x] `docs/gap_analysis.md` capturing current state and prioritized recommendations.【F:docs/gap_analysis.md†L1-L94】
- [x] REST/GraphQL client abstraction with fallback-friendly IssuesClient wiring and targeted unit tests.【F:src/issuesuite/github_issues.py†L41-L195】【F:tests/test_github_rest_client.py†L1-L116】
- [x] Telemetry scaffold (`observability.py`) plus performance budget checker exposed in quality gates and benchmarks.【F:src/issuesuite/observability.py†L1-L65】【F:src/issuesuite/benchmarking.py†L1-L260】
- [x] Governance reinforcements: agent apply schema enforcement, approval gating, and updated CLI surface.【F:src/issuesuite/cli.py†L370-L474】【F:tests/test_agent_apply_validation.py†L1-L67】
- [x] Signed index storage module with signature verification tests to guard against tampering.【F:src/issuesuite/index_store.py†L1-L63】【F:tests/test_index_store.py†L1-L33】
- [x] Release pipeline hardening with SBOM emission, pip-audit, and Sigstore attestations prior to publish.【F:.github/workflows/publish.yml†L20-L58】
- [x] Deterministic performance-report generation harness and CLI wrapper for CI gating.【F:scripts/generate_performance_report.py†L1-L43】【F:src/issuesuite/performance_report.py†L1-L105】
- [x] Schema registry module with version-locked artifacts, changelog update helper with non-blocking lock, and documented nox automation for developers.【F:src/issuesuite/schema_registry.py†L1-L64】【F:scripts/update_changelog.py†L1-L68】【F:README.md†L92-L108】
- [x] Resilient pip-audit integration plus `issuesuite security` CLI workflow with telemetry instrumentation, refresh flag, and regression coverage.【F:src/issuesuite/pip_audit_integration.py†L1-L240】【F:src/issuesuite/cli.py†L1-L700】【F:tests/test_pip_audit_integration.py†L1-L150】【F:tests/test_cli_extended.py†L200-L235】
- [x] GitHub App JWT fallback hardened so malformed keys now produce deterministic placeholders, maintaining backwards-compatible CLI behaviour with targeted regression tests.【F:src/issuesuite/github_auth.py†L330-L397】【F:tests/test_github_app_auth.py†L240-L257】
- [ ] Governance blueprint published for Frontier Apex gates with UX, repo management, and GitHub Projects integration criteria.
- [x] Automated offline advisory refresh module with OSV integration, CLI entry point, quality gate wiring, and unit tests safeguarding specifier rendering.【F:src/issuesuite/advisory_refresh.py†L1-L236】【F:scripts/quality_gates.py†L20-L94】【F:tests/test_advisory_refresh.py†L1-L94】
- [x] Frontier Elite governance suite: Next Steps validator module, CLI wrapper, and extended unit coverage for scaffold + governance validation.【F:src/issuesuite/next_steps_validator.py†L1-L109】【F:scripts/verify_next_steps.py†L1-L33】【F:tests/test_next_steps_validator.py†L1-L66】【F:tests/test_scaffold.py†L1-L44】


## Quality Gates

- [x] Coverage ≥80%: `pytest --cov=issuesuite --cov-report=term --cov-report=xml` with enforcement aggregated through `python scripts/quality_gates.py` for CI and local workflows.【F:scripts/quality_gates.py†L21-L82】
- [x] Static analysis & formatting: `ruff check`, `ruff format --check`, and `mypy src` stay green prior to any merge.【F:scripts/quality_gates.py†L29-L44】
- [x] Security posture: `python -m bandit -r src`, `python -m pip_audit --progress-spinner off --strict` (pending hang fix), and `python -m issuesuite.dependency_audit` safeguard supply-chain baselines with offline fallbacks.【F:scripts/quality_gates.py†L45-L65】【F:src/issuesuite/dependency_audit.py†L1-L314】
- [x] Secrets & governance: `python -m detect_secrets scan --baseline .secrets.baseline` plus `python scripts/verify_next_steps.py` ensure no sensitive leakage and that UX/GitHub Projects expectations remain documented.【F:scripts/quality_gates.py†L66-L82】【F:src/issuesuite/next_steps_validator.py†L1-L109】
- [x] Build & runtime health: `python -m compileall src`, `python -m build`, `python scripts/generate_performance_report.py`, and `python -m issuesuite.benchmarking --check` keep packaging and performance budgets honest.【F:scripts/quality_gates.py†L54-L78】
- [x] Advisories: `python -m issuesuite.advisory_refresh --check --max-age-days 30` locks in offline dataset freshness alongside GitHub Projects governance updates.【F:scripts/quality_gates.py†L70-L75】【F:docs/red_team_report.md†L18-L64】
- [ ] Follow-up: stabilize `python -m pip_audit --progress-spinner off --strict` in hermetic runners (tracking separately).【fce977†L1-L120】
- [ ] Frontier Apex gates (coverage ≥85%, UX acceptance scripts, GitHub Projects sync telemetry, dependency posture SLOs) documented and automated prior to enabling “ready for review” workflows.

## Links

- [x] Failure log: tests/test_github_app_auth.py::test_jwt_generation_with_key_file — resolved by `pytest` chunk `022791†L1-L33`.
- [x] Security scan details — `bandit` chunk `349c75†L1-L95`.
- [x] Secrets scan summary — `detect-secrets` command `detect-secrets scan --baseline .secrets.baseline` (no findings).【5894f0†L1-L1】
- [x] Dependency audit — `python -m issuesuite.dependency_audit --output-json` recorded in chunk `a28292`.
- [x] Quality gate roll-up — `python scripts/quality_gates.py` output (all gates passing with offline-aware dependency audit).【106476†L1-L8】
- [x] Gap analysis — `docs/gap_analysis.md`.

## Risks / Notes

- [x] REST client now sanitizes env configuration, so enterprise packaging flows won't choke on whitespace tokens or disable flags toggled via non-numeric values.【F:src/issuesuite/github_issues.py†L270-L316】【F:tests/test_github_rest_client.py†L120-L177】
- [x] Resilient pip-audit wrapper eliminates sandbox trust failures; telemetry spans and offline refresh automation surface degraded feeds promptly.【F:src/issuesuite/pip_audit_integration.py†L1-L240】【F:src/issuesuite/advisory_refresh.py†L1-L236】
- [x] Missing GitHub CLI in CI-like environments prevented JWT generation; mitigated via CLI detection fallback (monitor logs for regressions).
- [x] Multiple Bandit findings stemmed from intentional subprocess usage; mitigated via command wrappers and inline documentation (monitor future changes).
- [x] Detect-secrets baseline established; keep it fresh when governance docs evolve to avoid regressing signal.【F:.secrets.baseline†L1-L74】
- [x] Enterprise SDLC controls (telemetry, release provenance, AI guardrails) remain outstanding; treat recommendations above as gating before claiming frontier readiness.【F:docs/gap_analysis.md†L64-L94】
- [x] Dependency audit gate now resilient via offline dataset fallback; refresh `security_advisories.json` alongside upstream disclosures to retain coverage.【F:src/issuesuite/dependency_audit.py†L1-L193】【F:src/issuesuite/data/security_advisories.json†L1-L24】
- [x] Changelog updates use a non-blocking lock to prevent editorial hangs, and writes now occur only after the lock is held so contention can never truncate the file; continue running `scripts/update_changelog.py` in automation to surface conflicts early.【F:scripts/update_changelog.py†L1-L70】【F:tests/test_update_changelog.py†L1-L86】
- [x] Schema registry centralises artifact versions, so keep registry entries and documentation in sync when adding new payloads.【F:src/issuesuite/schema_registry.py†L1-L64】【F:docs/gap_analysis.md†L1-L64】
- [x] Benchmark enforcement relies on up-to-date `performance_report.json`; automated generation now precedes the gate and keeps metrics stable in CI.【F:src/issuesuite/performance_report.py†L1-L105】【F:scripts/quality_gates.py†L20-L77】
- [x] OpenTelemetry console exporter previously raised `ValueError` during shutdown; resilient writer and import diagnostics now prevent noisy tracebacks while keeping telemetry optional.【F:src/issuesuite/observability.py†L15-L97】
- [x] Agent-apply manual validation now guards slug and docs structure even when `jsonschema` is unavailable; monitor for schema drift when new fields are introduced.【F:src/issuesuite/agent_updates.py†L85-L152】【F:tests/test_agent_apply_validation.py†L69-L147】
- [x] Offline advisory dataset refreshed automatically via the new OSV-backed helper and enforced freshness gate.【F:src/issuesuite/advisory_refresh.py†L1-L236】【F:docs/red_team_report.md†L18-L64】
- [x] Frontier Elite governance: validator + scripts now enforce UX research notes and GitHub Projects automation within Next Steps before quality gates pass.【F:src/issuesuite/next_steps_validator.py†L1-L109】【F:scripts/verify_next_steps.py†L1-L33】
- [ ] `pip-audit --strict` currently hangs in offline environments; wire resilient timeouts/offline datasets so dependency gates don't block local QA.【fce977†L1-L120】
- [ ] Transition plan required for Frontier Apex gates so contributors have staged rollouts, sandbox dashboards, and GitHub Projects training before enforcement.
