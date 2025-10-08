# Index Mapping Design (.issuesuite/index.json)

Status: Draft
Owner: IssueSuite Maintainers
Last Updated: 2025-09-26

## Purpose

Maintain a durable mapping from `external_id` (spec slug) to GitHub issue number to preserve continuity when titles change and to accelerate lookups.

## File path

`.issuesuite/index.json`

## Format (version 1)

```json
{
  "version": 1,
  "generated_at": "2025-09-26T12:00:00Z",
  "repo": "<owner>/<repo>",
  "entries": {
    "api-timeouts": { "issue": 123, "hash": "abc123def4567890" },
    "search-caching": { "issue": 124, "hash": "def456abc7890123" }
  }
}
```

### Fields

- `version`: Schema revision (start at 1).
- `generated_at`: Timestamp of last full write (UTC ISO 8601).
- `repo`: Repository identifier if available (optional for local only).
- `entries`: Object mapping slug IDs to entry objects.
  - `issue`: Integer issue number.
  - `hash`: Last known spec hash (truncated SHA-256) to enable quick skip decisions and drift detection.

## Lifecycle

1. Load existing index if present (ignore on corruption—start fresh).
2. After a successful non-dry-run sync:
   - For each created spec: add a new entry with issue number + hash.
   - For each updated spec: update the stored hash.
   - For each removed spec: stale entries are pruned by the orchestrator on subsequent non-dry-run syncs.
3. Persist atomically (write to temp file then rename).

## Atomic write strategy

- Write to `.issuesuite/index.json.tmp` then call `os.replace` to the final path so readers never observe a partial file.

## Snapshot threshold

The orchestrator includes a `mapping_snapshot` in enriched summaries when the mapping size is below a configurable threshold (default 500). Larger mappings include size metadata only.

## Error handling

- On JSON decode errors: log a warning and treat the index as empty.
- On write failure: surface the error but do not abort sync results already printed (best-effort persistence).

## Integration points

- `core.sync()` after summary assembly and before hash-state persistence (or combined with hash state into a unified file in a later revision).
- `ai-context` export optionally surfaces the current mapping size and version.

## Future extensions

- Add `closed` boolean for retired external IDs.
- Add `project_item` for project integration caching.
- Add `labels_snapshot` for auditing label churn.
- Merge with the existing hash-state file to reduce file count.

## Open questions

- Should mapping removal occur when a spec disappears? (Proposal: keep for historical tracing; rely on a manual prune command.)
- Should we embed a checksum of the entire index for corruption detection? (Deferred.)

## Implementation plan

1. Maintain this design document.
2. Implement loader + saver (pure functions) with tests.
3. Integrate into the sync pipeline (create/update only).
4. Expose a summary metric (mapping size) in `ai-context`.
5. Evaluate merging with hash state after stability.
