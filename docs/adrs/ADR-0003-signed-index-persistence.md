---
id: ADR-0003
title: Signed index persistence with signature verification
status: Accepted
decision_date: 2025-10-20
authors:
  - IssueSuite Maintainers
---

## Context

IssueSuite maintains a slug→issue number mapping (`.issuesuite/index.json`) to enable idempotent syncs. In distributed teams, malicious or accidental corruption of this mapping could cause issue duplication or sync failures. We needed an integrity layer to detect tampering and support optional remote mirroring.

## Decision

Introduce `issuesuite.index_store` with signature verification support. The index document can optionally include a `signature` field computed from the mapping JSON using a shared secret. The store validates signatures on load and rejects tampered indices. A companion `issuesuite.mapping_utils` module provides helpers for pruning stale entries without violating complexity limits.

## Consequences

- Index tampering is detectable via signature verification (when enabled).
- Distributed teams can mirror the index to remote storage (future enhancement).
- Signature keys must be managed securely (environment variables or key management services).
- Tests guard against signature mismatches and ensure pruning logic is deterministic.

## Follow-up work

- Implement remote index mirroring (e.g., S3, GitHub Gist) for durability.
- Document key rotation procedures and recovery workflows.
- Add ADR linking signature verification with rollback strategies for distributed teams.
