---
id: ADR-0002
title: Adopt explicit schema versioning and registry
status: Accepted
decision_date: 2025-10-18
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite exports multiple JSON artifacts (issue specs, change summaries, AI context) consumed by downstream automation and AI tooling. Without version metadata, consumers cannot reliably parse artifacts or detect breaking changes. We needed a centralized registry to expose schemas with explicit versions and prevent silent incompatibilities.

## Decision

Introduce `issuesuite.schema_registry` to maintain a version-locked mapping of schema names to their metadata (version strings, descriptions). Each artifact now includes a `schemaVersion` field (e.g., `ai-context/1`, `export/1`) allowing consumers to validate compatibility before parsing. The registry is queryable via `get_schemas()` and emitted by the `issuesuite schema` command.

## Consequences

- All JSON outputs include explicit `schemaVersion` and `type` fields.
- Consumers can gate on schema version to handle format evolution gracefully.
- Breaking schema changes require bumping the version number and documenting migrations.
- The registry serves as the single source of truth for artifact formats.

## Follow-up work

- Document migration paths when bumping schema versions.
- Extend the registry to include validation hooks (e.g., JSON Schema references).
- Surface schema metadata in the Starlight documentation site.
