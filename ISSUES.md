# IssueSuite Roadmap (Source of Truth)

This file is the canonical definition of desired GitHub Issues and (optionally) their Project field values.

Each issue is expressed as a Markdown heading followed immediately by a fenced YAML block.

Conventions:

- Heading level 2 (##) defines a unique slug via bracket notation: `## [slug: some-slug]`
- Slug must be unique, lowercase, kebab-case.
- YAML keys supported (initial minimal schema):
  - title (string, required)
  - body (string or folded block, optional)
  - labels (list[str], optional)
  - assignees (list[str], optional)
  - milestone (string, optional)
  - project (mapping, optional):
    owner: "@org-or-user" # org or user handle (prefix @ for clarity)
    number: 1 # GitHub Project (new) project number
    fields: # Mapping of Project field name -> value / option name
    Status: Todo
    Priority: High

A hidden marker will be injected into created issue bodies: `<!-- issuesuite:slug=<slug> -->`.

This enables idempotent lookups even if title changes.

(Generated initial template – extend or edit at will.)

---

## [slug: initial-setup]

```yaml
title: Initial repository setup
body: >
  Track the foundational tasks needed to make IssueSuite fully operational.
labels: [meta]
assignees: []
milestone: Backlog
project:
  owner: "@your-org"
  number: 1
  fields:
    Status: Todo
    Priority: High
```

## [slug: project-assignment]

```yaml
title: Implement real project assignment
body: >
  After creating an issue via REST, fetch its node ID and add it to the configured GitHub Project.
  Then update single-select / text fields as declared in ISSUES.md.
labels: [feature, projects]
assignees: []
project:
  owner: "@your-org"
  number: 1
  fields:
    Status: Todo
    Priority: Medium
```

## [slug: ai-context-schema]

```yaml
title: Plan ai-context schema bump
body: >
  Evaluate adding project field metadata (field id, option ids) to ai-context output and bump schema version.
labels: [enhancement, ai]
assignees: []
project:
  owner: "@your-org"
  number: 1
  fields:
    Status: Backlog
    Priority: Low
```
