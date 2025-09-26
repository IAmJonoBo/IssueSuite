# Index Mapping Design (.issuesuite/index.json)

Status: Draft
Owner: IssueSuite Maintainers
Last Updated: 2025-09-26

## Purpose

Maintain a durable mapping from `external_id` (spec slug / numeric ID) to GitHub issue number (int) to preserve continuity when titles change and to accelerate lookups.

## File Path

`.issuesuite/index.json`

## Format (Version 1)

```json
{
  "version": 1,
  "generated_at": "2025-09-26T12:00:00Z",  // ISO8601
  "repo": "<owner>/<repo>",
  "entries": {
    "001": { "issue": 123, "hash": "abc123def4567890" },
    "002": { "issue": 124, "hash": "def456abc7890123" }
  }
}
```

### Fields

- `version`: Schema revision (start at 1).
- `generated_at`: Timestamp of last full write (UTC ISO8601).
- `repo`: Repository identifier if available (optional for local only).
- `entries`: Object mapping string external IDs to entry objects.
  - `issue`: Integer issue number.
  - `hash`: Last known spec hash (truncated SHA-256) to enable quick skip decisions and drift detection.

## Lifecycle

1. Load existing index if present (ignore on corruption – start fresh).

1. After a successful non-dry-run sync:

- For each created spec: add new entry with issue number + hash.
- For each updated spec: update hash.
- For each closed spec (if closed by removal and not reused): optionally keep (historical) or mark with `"closed": true` (future enhancement).

1. Persist atomically (write to temp file then rename).

## Atomic Write Strategy

- Write to `.issuesuite/index.json.tmp` then `os.replace` to final path.
- Ensures readers never see partial file.

## Concurrency Considerations

Current CLI use is single-process; if future parallel invocations arise, a simple file lock (`.issuesuite/index.lock`) can gate writes.

## Error Handling

- On JSON decode error: log warning and treat as empty index.
- On write failure: surface error but do not abort sync results already printed (best-effort persistence).

## Integration Points

- `core.sync()` after summary assembly and before hash state save (or combined with hash state into unified file in a later revision).
- `ai-context` export could optionally surface current mapping size and version.

## Future Extensions

- Add `closed` boolean for retired external IDs.
- Add `project_item` for future project integration caching.
- Add `labels_snapshot` for auditing label churn.
- Merge with existing hash state file to reduce file count.

## Open Questions

- Should mapping removal occur when a spec disappears? (Proposal: keep for historical tracing; rely on manual prune command.)
- Should we embed a checksum of the entire index for corruption detection? (Deferred.)

## Implementation Plan (Phased)

1. Introduce design doc (this file).
2. Implement loader + saver (pure functions) with tests.
3. Integrate into sync pipeline (create/update only).
4. Expose summary metric (mapping size) in `ai-context`.
5. Evaluate merging with hash state after stability.
