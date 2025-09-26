# IssueSuite — Copilot Instruction Template (vNext)

**Intent:** Make IssueSuite a pip‑installable CLI that **syncs `ISSUES.md` ⇄ GitHub Issues ⇄ GitHub Projects (v2)**, is **idempotent**, and runs cleanly **locally, in CI, Codespaces/devcontainers, and Copilot’s repo‑scoped environment**. **Do not browse the web**; use this brief and the repo context only.

## Non‑negotiables

- Single source of truth: `ISSUES.md` (fenced YAML blocks per item).
- Idempotency markers in issue bodies: `<!-- issuesuite:slug=<slug> -->` and local map `.issuesuite/index.json`.
- REST for Issues; GraphQL for Projects v2. Add item → then update fields (never in the same call).
- Dry runs by default in CI; explicit apply step.
- Least‑privilege tokens and explicit Actions permissions.

---

## Sprint Plan (recommendation)

### Sprint 0 — Repo hygiene & packaging (Day 0–1)

**Scope**

- Convert to `src/` layout: `src/issuesuite/` with `__init__.py` and `__main__.py` exposing `main()`.
- Add `pyproject.toml` (PEP 621; `hatchling`), `README.md`, `LICENSE`.
- Add `.devcontainer/devcontainer.json` (Python, `gh`, `jq`).
- Pre-commit: `ruff`, `black`, `mypy` (optional), `pyproject-fmt`.
- Build and metadata checks: `python -m build` and `twine check`.

**Quality gates / DoD**

- `pip install -e .` works; `issuesuite --help` prints.
- `python -m build` creates sdist+wheel; `twine check dist/*` passes.
- Devcontainer opens and runs `issuesuite` without extra setup.

---

### Sprint 1 — Parser, schema, and idempotency (Day 1–2)

**Scope**

- Define `ISSUES.md` schema (per-item fenced YAML):

  ````markdown
  ## [slug: api-timeouts]

  ```yaml
  title: Investigate API timeouts
  body: >
    Requests intermittently exceed 5s…
  labels: [bug, backend]
  assignees: []
  milestone: Backlog
  project:
    owner: "@me" # org/user handle
    number: 1 # Project number
    fields:
      Status: Todo
      Priority: High
  ```
  ````

  ```

  ```

- Parser yields `DesiredItem{slug, title, body, labels, assignees, milestone, project{owner, number, fields{…}}}`.

- Maintain `.issuesuite/index.json` → `{slug -> issue_number}`.
- Insert/update hidden marker in issue body.

**Quality gates / DoD**

- Unit tests for parser (valid, malformed, missing fields).
- Stable round‑trip: parse → render diff → no changes when re‑parsed.

---

### Sprint 2 — Issues (REST) CRUD (Day 2–3)

**Scope**

- Implement `create_or_update_issue(item)` with REST (`POST /repos/{owner}/{repo}/issues`, `PATCH /repos/{owner}/{repo}/issues/{number}`).
- Support labels, assignees, milestone, body with marker, and close when item removed (with `--prune`).
- CLI: `issuesuite sync --repo <owner/repo> --dry` (default) and `--apply`.

**Quality gates / DoD**

- Dry run shows table of `create/update/no‑op/close` with reasons.
- Skips no‑ops by hashing (title/body/labels/milestone) to reduce writes.
- Integration test behind `GITHUB_TOKEN` against a test repo.

---

### Sprint 3 — Projects v2 (GraphQL) (Day 3–4)

**Scope**

- Look up `projectId` by owner+number.
- Ensure Issue exists → add item: `addProjectV2ItemById(projectId, contentId)`.
- Update fields per type: single‑select (optionId), text, number, date, iteration (iterationId).
- Cache `fieldId` and option/iteration IDs; expose `--project-owner/--project-number` flags.

**Quality gates / DoD**

- Verified sequence: add → then update fields. No mixed calls.
- Field cache prevents N+1 GraphQL calls.
- Dry run prints intended field changes; apply updates correctly.

---

### Sprint 4 — CI & release automation (Day 4)

**Scope**

- `.github/workflows/issuesuite-sync.yml` with explicit permissions and path filters.
- Steps: checkout → `pip install -e .` → `issuesuite sync --dry` → `issuesuite sync --apply`.
- Trusted Publishing release workflow (tag `v*`) to PyPI.
- Composite Action `issuesuite-action` (installs and runs `sync`).

**Quality gates / DoD**

- On change to `ISSUES.md` or config, workflow runs and reports a diff.
- Release pipeline produces wheel+sdist and publishes on tag.

**Sample (edit as needed)**

```yaml
name: IssueSuite Sync
on:
  push:
    branches: [main, v2]
    paths:
      [
        "ISSUES.md",
        "pyproject.toml",
        "src/**",
        ".github/workflows/issuesuite-sync.yml",
      ]
  workflow_dispatch:
permissions:
  contents: read
  issues: write
  repository-projects: write
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: python -m pip install --upgrade pip
      - run: pip install -e .
      - run: issuesuite sync --dry --repo ${{ github.repository }}
      - run: issuesuite sync --apply --repo ${{ github.repository }}
```

---

### Sprint 5 — Two‑way sync & reconcile (Day 5–6)

**Scope**

- Webhooks: subscribe to `issues` and `projects_v2_item` to detect drift.
- New commands:
  - `issuesuite import` → generate draft `ISSUES.md` from live Issues (labels/milestones/project fields).
  - `issuesuite reconcile` → compare live vs file; produce readable diff and optional PR comment.
  - `issuesuite doctor` → validate token scopes, project/field IDs, webhook delivery health.

**Quality gates / DoD**

- Reconcile never overwrites; prints action plan and exit codes.
- PR comment includes summary table and next steps.

---

### Sprint 6 — Resilience, rate limits, and UX polish (Day 6)

**Scope**

- Backoff on rate/abuse limits (respect `Retry-After`; jittered exponential backoff).
- Clear error taxonomy: auth scope, missing field, unknown option, network.
- CLI flags: `--dry`, `--apply`, `--repo`, `--project-owner`, `--project-number`, `--summary-json`.
- Structured logs (JSON lines): `ts, action, slug, issue#, projectItemId, hash, status`.

**Quality gates / DoD**

- Simulated 429/403 paths verified; no unhandled exceptions.
- Logs parseable and redaction of tokens enforced.

---

### Sprint 7 — DX: gh extension, docs, Copilot guide (Day 7)

**Scope**

- Publish `gh-issuesuite` extension wrapper: `gh issuesuite sync`.
- `/docs/ISSUESUITE_GUIDE.md` with copy‑ready Copilot prompts, failure triage, and token matrix.
- README quick start and examples; badges for PyPI and Action.

**Quality gates / DoD**

- `gh issuesuite sync` works if `gh` is present; otherwise Python CLI path works.
- Docs complete enough for repo‑scoped Copilot to operate without browsing.

---

## Cross‑cutting Quality Gates

- **Security:** workflows use least‑privilege `permissions:`; secrets unneeded except optional PAT.
- **Idempotency:** no-op detection via content hash; marker preserved; index.json updated atomically.
- **Tests:** unit (parser, hashing, diff), integration (guarded by env vars), golden files for diff output.
- **Observability:** `--summary-json` artefact uploaded in CI; optional Grafana later.
- **Performance:** batch reads; cached field/option IDs; skip writes on no‑op.

---

## Auth & Permissions Matrix (reference for humans; Copilot relies on this brief)

- **GitHub Actions `GITHUB_TOKEN`:** set job permissions: `contents: read`, `issues: write`, `repository-projects: write`.
- **PAT / Fine‑grained PAT:** must allow Issues write and Projects write (org policy may gate this).
- **GitHub App (optional):** alternative when PAT scopes are restricted.

---

## CLI Surface (current + planned)

- `issuesuite sync [--dry|--apply] [--repo <owner/repo>] [--project-owner <owner>] [--project-number <n>] [--summary-json <path>] [--prune]`
- `issuesuite import [--repo <owner/repo>] [--project-owner <owner>] [--project-number <n>]`
- `issuesuite reconcile [--repo …]`
- `issuesuite doctor`

---

## Minimal GraphQL examples (for `gh api`)

```bash
# 1) Get projectId
gh api graphql -f query='query($o:String!,$n:Int!){ organization(login:$o){ projectV2(number:$n){ id } } }' \
  -f o=ACME -F n=1 -q '.data.organization.projectV2.id'

# 2) Add issue to project
gh api graphql -f query='mutation($p:ID!,$c:ID!){ addProjectV2ItemById(input:{projectId:$p, contentId:$c}){ item { id } } }' \
  -f p=$PROJECT_ID -f c=$ISSUE_NODE_ID -q '.data.addProjectV2ItemById.item.id'

# 3) Update a single-select field
gh api graphql -f query='mutation($p:ID!,$i:ID!,$f:ID!,$o:ID!){ updateProjectV2ItemFieldValue(input:{projectId:$p, itemId:$i, fieldId:$f, value:{singleSelectOptionId:$o}}){ projectV2Item { id } } }' \
  -f p=$PROJECT_ID -f i=$ITEM_ID -f f=$FIELD_ID -f o=$OPTION_ID
```

---

## Failure triage (fast checks)

- **Missing scopes/permissions** → cannot add to Projects: adjust workflow `permissions:` or token scopes.
- **Wrong sequence** → setting fields while adding item: split into two calls.
- **Unknown field/option** → list fields/options first; cache IDs; map name → ID.
- **Rate limits** → respect `Retry-After`; backoff and retry with jitter; reduce write frequency by hashing.
- **Copilot cannot browse** → keep this file and `/docs/ISSUESUITE_GUIDE.md` current; include example inputs.

---

## Quick wins (apply immediately)

- Implement field/option **ID cache** and **no‑op skip** before large syncs.
- Add `path` filters in workflow to only run on `ISSUES.md` and config/code changes.
- Ensure `v2` branch exists; never include `"v2"` in any search strings.

```

```
