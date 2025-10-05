"""High-level orchestration utilities bridging legacy script CLI and library.

Centralizes sync behavior (hash state + mapping + summary JSON) while keeping
public API surface minimal. The enriched summary mirrors prior script output
with additional metadata for AI and future reconcile features.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from .config import SuiteConfig
from .core import IssueSuite
from .index_store import IndexDocument, load_index_document, persist_index_document

logger = logging.getLogger(__name__)

# Threshold for including full mapping snapshot inline in enriched summary output
MAPPING_SNAPSHOT_THRESHOLD = 500


# --- Typed schema objects -------------------------------------------------


class ChangeEntry(TypedDict, total=False):
    external_id: str
    action: str  # created / updated / closed / unchanged (if ever exposed)
    diff: dict[str, Any]


class ChangeSet(TypedDict, total=False):
    created: list[ChangeEntry]
    updated: list[ChangeEntry]
    closed: list[ChangeEntry]


class Totals(TypedDict):
    created: int
    updated: int
    closed: int
    unchanged: int
    parsed: int


class BaseSummary(TypedDict, total=False):
    totals: Totals
    changes: ChangeSet
    mapping: dict[str, int]


class EnrichedSummary(BaseSummary, total=False):
    schemaVersion: int
    generated_at: str
    dry_run: bool
    ai_mode: bool
    mapping_present: bool
    mapping_size: int
    mapping_snapshot: dict[str, int]
    mapping_signature: str
    # last_error is optional and only present when sync failed
    last_error: Any


# -------------------------------------------------------------------------


def _iter_updated_entries(summary: dict[str, Any]) -> list[dict[str, Any]]:  # retain dynamic helper
    """Return list of updated change entries (each a dict) or empty list.

    This isolates dynamic JSON shape handling so type/lint noise is localized.
    """
    changes = summary.get("changes")
    if not isinstance(changes, dict):
        return []
    updated_any = changes.get("updated")
    if not isinstance(updated_any, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in updated_any:
        if isinstance(entry, dict):  # narrow type
            out.append(entry)  # safe append
    return out


def _load_index_document(cfg: SuiteConfig) -> IndexDocument:
    idx_file = cfg.source_file.parent / ".issuesuite" / "index.json"
    doc = load_index_document(idx_file)
    if not doc.repo and cfg.github_repo:
        doc.repo = cfg.github_repo
    return doc


def _truncate_body_diffs(summary: dict[str, Any], truncate: int | None) -> None:
    """Apply body diff truncation in-place respecting configured limit."""
    if not truncate:
        return
    for entry in _iter_updated_entries(summary):
        diff_obj_any = entry.get("diff")
        if not isinstance(diff_obj_any, dict):
            continue
        body_diff_any = diff_obj_any.get("body_diff")
        if not isinstance(body_diff_any, list):
            continue
        if len(body_diff_any) <= truncate:
            continue
        diff_obj_any["body_diff"] = [str(x) for x in body_diff_any[:truncate]] + ["... (truncated)"]


def _resolve_output_path(base_dir: Path, candidate: str | os.PathLike[str]) -> Path:
    path = Path(candidate)
    if not path.is_absolute():
        path = base_dir / path
    return path


def _persist_mapping(
    cfg: SuiteConfig,
    mapping: dict[str, int],
    *,
    mapping_path: str | None,
) -> None:
    """Persist mapping to legacy path and canonical signed index document."""
    base_dir = cfg.source_file.parent
    legacy_target = mapping_path or cfg.mapping_file
    legacy_mp = _resolve_output_path(base_dir, legacy_target)
    legacy_mp.parent.mkdir(parents=True, exist_ok=True)
    legacy_mp.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    index_dir = base_dir / ".issuesuite"
    index_dir.mkdir(exist_ok=True)
    index_path = index_dir / "index.json"
    mirror_env = os.environ.get("ISSUESUITE_INDEX_MIRROR")
    mirror_path = None
    if mirror_env:
        mirror_candidate = _resolve_output_path(base_dir, mirror_env)
        mirror_candidate.parent.mkdir(parents=True, exist_ok=True)
        mirror_path = mirror_candidate
    doc = IndexDocument(entries={k: {"issue": v} for k, v in mapping.items()}, repo=cfg.github_repo)
    persist_index_document(index_path, doc, mirror=mirror_path)


def _normalize_mapping(
    source: Any,
    *,
    context: str,
    value_getter: Callable[[Any], Any] | None = None,
) -> dict[str, int]:
    """Coerce a mapping-like object into ``slug -> issue`` integers."""

    if not isinstance(source, dict):
        return {}

    result: dict[str, int] = {}
    for raw_key, raw_value in source.items():
        candidate = raw_value
        if value_getter is not None:
            try:
                candidate = value_getter(raw_value)
            except Exception:  # pragma: no cover - defensive guard
                logger.debug(
                    "Skipping mapping entry %s from %s due to value getter error",
                    raw_key,
                    context,
                )
                continue
        try:
            result[str(raw_key)] = int(candidate)
        except (TypeError, ValueError):
            logger.debug("Skipping invalid mapping entry %s from %s", raw_key, context)
    return result


def _prune_stale_entries(mapping: dict[str, int], active_slugs: set[str]) -> None:
    """Remove mapping entries that no longer appear in the active slug set."""

    if not mapping or not active_slugs:
        return

    for slug in list(mapping.keys()):
        if slug not in active_slugs:
            mapping.pop(slug, None)


def sync_with_summary(
    cfg: SuiteConfig,
    *,
    dry_run: bool,
    update: bool,
    respect_status: bool,
    preflight: bool,
    summary_path: str | None = None,
    mapping_path: str | None = None,
    prune: bool = False,
) -> EnrichedSummary:
    """Run a sync and emit enriched summary JSON + (optional) mapping persistence.

    Kept intentionally linear; complex branches factored into helpers.
    """
    ai_mode = os.environ.get("ISSUESUITE_AI_MODE") == "1"
    effective_dry_run = True if ai_mode else dry_run

    suite = IssueSuite(cfg)
    summary_raw = suite.sync(
        dry_run=effective_dry_run,
        update=update,
        respect_status=respect_status,
        preflight=preflight,
        prune=prune,
    )

    # Merge existing mapping (from prior runs) with this run's mapping and prune stale.
    index_doc = _load_index_document(cfg)
    index_mapping = _normalize_mapping(
        index_doc.entries,
        context="index document",
        value_getter=lambda value: value.get("issue") if isinstance(value, dict) else value,
    )
    latest_mapping = _normalize_mapping(
        summary_raw.get("mapping"),
        context="sync summary",
    )
    current_slugs = set(latest_mapping)
    _prune_stale_entries(index_mapping, current_slugs)
    if latest_mapping:
        index_mapping.update(latest_mapping)

    # Truncate body diffs if configured
    _truncate_body_diffs(summary_raw, cfg.truncate_body_diff)

    # Persist mapping only if not an effective dry-run (write merged/pruned set)
    if not effective_dry_run and index_mapping:
        _persist_mapping(cfg, index_mapping, mapping_path=mapping_path)

    # summary_raw is a plain dict produced by IssueSuite.sync; selective unpack
    # Note: dynamic dict assembly; rely on runtime shape not strict static typing here.
    enriched: EnrichedSummary = {
        'schemaVersion': cfg.schema_version,
        'generated_at': datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'dry_run': effective_dry_run,
        'ai_mode': ai_mode,
        'mapping_present': bool(index_mapping),
        'mapping_size': len(index_mapping),
        'mapping_signature': getattr(index_doc, 'signature', ''),
        'totals': summary_raw.get('totals', {}),
        'changes': summary_raw.get('changes', {}),
        'mapping': summary_raw.get('mapping', {}),
    }
    if index_mapping and len(index_mapping) <= MAPPING_SNAPSHOT_THRESHOLD:
        enriched["mapping_snapshot"] = dict(index_mapping)

    # Attach last error if surfaced by suite (only populated on failure path, so none on success)
    if getattr(suite, '_last_error', None):  # attribute is best-effort internal
        le = suite._last_error  # may be None
        if isinstance(le, dict):
            enriched['last_error'] = le
    base_dir = cfg.source_file.parent
    target_summary = summary_path or cfg.summary_json
    sp = _resolve_output_path(base_dir, target_summary)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")
    return enriched
