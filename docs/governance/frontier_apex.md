# Frontier Apex Governance Blueprint

The Frontier Apex layer evolves IssueSuite's "Frontier Elite" guardrails into a
programmatic standard covering code quality, UX governance, portfolio planning,
and release provenance. This document codifies the next wave of requirements so
teams can forecast the rollout, wire automation, and measure success.

## Outcomes & Success Metrics

| Track | Target | Measurement |
| ----- | ------ | ----------- |
| Coverage | ≥ 85% line coverage with critical modules ≥ 90% | `pytest --cov=issuesuite` enforced via `scripts/quality_gates.py` with per-module thresholds surfaced in `coverage.json`. |
| Type Safety | ≥ 90% of modules included in `mypy` strict mode with drift telemetry | `python -m mypy src --strict` baseline plus `scripts/type_coverage_report.py` (to be implemented) uploaded as PR check artifact. |
| UX & Accessibility | All CLI commands & docs validated by automated UX acceptance harness | `python scripts/ux_acceptance.py` verifying accessibility heuristics, terminal help formatting, and docs navigability. |
| GitHub Projects Automation | Declarative project sync with status SLIs | Nightly workflow posts project health metrics (open vs closed, SLA) to GitHub Projects dashboards. |
| Dependency Hygiene | Offline + online advisory parity, SBOM & provenance gating | `issuesuite security --pip-audit` + curated advisories; SBOM hashed and attested in release pipelines. |
| Program Management Traceability | Next Steps, Projects, and Releases linked bidirectionally | Automation reconciles `/Next Steps.md`, GitHub Projects, and release notes each cycle. |

## Capability Pillars

### 1. Coverage & Type Telemetry

- Extend `scripts/quality_gates.py` to parse `coverage.xml` and fail when
  high-priority modules (`core`, `cli`, `github_issues`, `project`,
  `pip_audit_integration`) drop below 90%.
- Prototype landed: module thresholds now enforced via
  `scripts/quality_gates.py` with summaries emitted to
  `coverage_summary.json` for telemetry dashboards.
- Introduce `scripts/coverage_trends.py` to push historical coverage into the
  GitHub Projects dashboard and send alerts on 1% regressions. ✅ Implemented;
  the exporter now produces `coverage_trends.json` history, a
  `coverage_trends_latest.json` snapshot, and a `coverage_projects_payload.json`
  summary for automation hooks.
- Add a strict `mypy` session (`nox -s mypy_strict`) and require green status
  before the "Ready for review" label can be applied.
- Instrument `issuesuite.logging` to emit `type_check` telemetry after each
  invocation with module coverage stats for observability.
- Prototype landed: `scripts/type_coverage_report.py` exports strict-mode
  telemetry while `issuesuite.logging.StructuredLogger.log_type_check_metrics`
  now emits the snapshot when logging is configured.

### 2. UX and Accessibility Validation

- Build `scripts/ux_acceptance.py` which executes `issuesuite --help` for each
  command, checking ANSI contrast, width (≤ 100 columns), and exit codes.
- Prototype landed: the acceptance harness runs as part of the quality gates
  and publishes `ux_acceptance_report.json` for future dashboards.
- Create Markdown lint rules to enforce heading hierarchy, alt-text, and task
  list completeness across `/docs` and `/Next Steps.md`.
- Capture CLI interaction traces in `docs/reference/cli.md` and embed them in
  regression tests to guard UX regressions.
- Add VS Code tasks for "UX Acceptance" and wire them into GitHub Actions via a
  reusable workflow.

### 3. GitHub Projects Automation

- Expand `GitHubProjectAssigner` to persist GraphQL node IDs using the REST
  client instead of shelling out to `gh`.
- Implement `scripts/projects_status_report.py` that syncs project metrics and
  attaches JSON summaries to pull requests.
- Expose the same automation as `issuesuite projects-status` so operators can
  generate artifacts without invoking standalone scripts.
- Prototype landed: `scripts/projects_status_report.py` and `issuesuite
  projects-status` now generate `projects_status_report.json` and a Markdown
  summary by merging coverage telemetry with `/Next Steps.md`, paving the way
  for nightly automation.
- Configure a scheduled workflow (`.github/workflows/projects-daily.yml`) to
  refresh project dashboards, annotate risks, and backfill timeline milestones.
- Document runbooks for incident response when automation detects stale project
  items (alerts routed through GitHub Issues and Slack).

### 4. Dependency & Supply Chain Hardening

- Promote the curated advisory dataset to a versioned artifact with checksum
  verification during CI runs.
- Require CycloneDX SBOM generation (`pip-audit -f cyclonedx-json`) on every
  release, storing provenance attestations alongside wheels and source
  distributions.
- Integrate `issuesuite.dependency_audit` results into a SARIF upload so
  GitHub Security dashboards highlight drift immediately.
- Add fallback trust policies and verification for offline advisories to ensure
  parity with upstream feeds.

### 5. Program Management & Governance

- Maintain `/Next Steps.md` as the canonical OKR ledger; automation checks for
  owner, due date, and status alignment with GitHub Projects.
- Record coverage, UX, and dependency scores in the GitHub Projects dashboard
  for each epic, using color-coded fields for SLO adherence.
- Expand the PR template with sections for UX acceptance, accessibility notes,
  and project alignment.
- Publish a quarterly governance review referencing this blueprint with actions
  for the subsequent increment.

## Rollout Phases

1. **Blueprint & Tooling (current)**
   - Publish this blueprint, align stakeholders, and seed backlog items in
     `/Next Steps.md`.
   - Prototype coverage threshold enforcement and strict mypy runs locally.

2. **Automation Beta (next 30 days)**
   - Land UX acceptance harness and Projects reporting scripts.
   - Run nightly GitHub Projects sync in shadow mode, comparing results against
     manual dashboards.

3. **Enforcement (next 60 days)**
   - Flip the "Frontier Apex" quality gate requiring all metrics to pass before
     merge.
   - Enable PR comment bots summarizing coverage/type/UX deltas.

4. **Continuous Improvement (ongoing)**
   - Iterate on thresholds (e.g., coverage ≥ 90%) once stability proven.
   - Expand telemetry exports (OpenTelemetry traces, metrics) for dashboards.

## Dependencies & Risks

- **Tooling Complexity:** Additional scripts increase maintenance surface.
  Mitigation: co-locate utilities in `scripts/` with shared logging and testing.
- **CI Runtime:** New gates may extend CI runtimes; baseline and optimize using
  cached environments and incremental checks.
- **Project API Limits:** Increased GitHub API traffic requires rate limit
  budgeting and retries; reuse `issuesuite.retry` with exponential backoff.
- **Contributor Onboarding:** Higher bars demand documentation and templates;
  update onboarding guides and preflight scripts accordingly.

## Next Actions

1. Implement strict coverage thresholds in `scripts/quality_gates.py`.
2. Scaffold UX acceptance harness and add corresponding GitHub Action.
3. Draft GitHub Projects automation workflow and metrics reporter.
4. Plan SBOM + provenance attestation integration with release pipeline.
5. Update `/Next Steps.md` to track Frontier Apex epics and owners.
