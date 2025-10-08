"""High-level orchestration utilities bridging legacy script CLI and library.

Centralizes sync behavior (hash state + mapping + summary JSON) while keeping
public API surface minimal. The enriched summary mirrors prior script output
with additional metadata for AI and future reconcile features.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict, cast

from .config import SuiteConfig
from .core import IssueSuite
from .index_store import IndexDocument, load_index_document, persist_index_document
from .logging import get_logger

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
    plan: list[dict[str, Any]]
    # last_error is optional and only present when sync failed
    last_error: Any


# -------------------------------------------------------------------------


def _iter_updated_entries(
    summary: dict[str, Any],
) -> list[dict[str, Any]]:  # retain dynamic helper
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


def _load_index_mapping(cfg: SuiteConfig) -> dict[str, int]:
    """Load existing index mapping; non-fatal on any error."""
    idx_file = cfg.source_file.parent / ".issuesuite" / "index.json"
    if not idx_file.exists():
        return {}
    doc = load_index_document(idx_file)
    result: dict[str, int] = {}
    for slug, payload in doc.entries.items():
        issue_value: Any = payload.get("issue") if isinstance(payload, dict) else payload
        try:
            result[str(slug)] = int(issue_value)
        except Exception:
            continue
    if result:
        return result
    try:
        raw_any: Any = json.loads(idx_file.read_text())
    except Exception:
        return {}
    if not isinstance(raw_any, dict):
        return {}
    raw_map = raw_any.get("mapping")
    if not isinstance(raw_map, dict):
        return {}
    for slug, value in raw_map.items():
        try:
            result[str(slug)] = int(value)
        except Exception:
            continue
    return result


def _normalize_mapping(
    raw: Mapping[Any, Any],
    *,
    context: str,
    value_getter: Callable[[Any], Any],
) -> dict[str, int]:
    """Normalize arbitrary mapping objects to ``{slug: issue_number}``."""

    normalized: dict[str, int] = {}
    for slug, value in raw.items():
        if not isinstance(slug, str):
            continue
        try:
            extracted = value_getter(value)
        except Exception:  # pragma: no cover - defensive guard
            continue
        try:
            normalized[slug] = int(extracted)
        except Exception:  # pragma: no cover - incompatible value shape
            continue
    if len(normalized) != len(raw):
        get_logger().debug(
            "mapping_normalized",
            context=context,
            normalized=len(normalized),
            dropped=len(raw) - len(normalized),
        )
    return normalized


def _prune_stale_entries(mapping: dict[str, int], current_slugs: set[str]) -> None:
    """Remove mapping entries whose slugs are no longer present."""

    stale = [slug for slug in mapping if slug not in current_slugs]
    for slug in stale:
        mapping.pop(slug, None)


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


def _persist_mapping(
    cfg: SuiteConfig,
    mapping: dict[str, int],
    *,
    mapping_path: str | None,
) -> None:
    """Persist mapping to legacy path and canonical index.json."""
    legacy_mp = Path(mapping_path or cfg.mapping_file)
    legacy_mp.parent.mkdir(parents=True, exist_ok=True)
    legacy_mp.write_text(json.dumps(mapping, indent=2) + "\n")
    index_dir = cfg.source_file.parent / ".issuesuite"
    index_dir.mkdir(exist_ok=True)
    entries = {slug: {"issue": issue} for slug, issue in mapping.items()}
    index_path = index_dir / "index.json"
    mirror_env = os.environ.get("ISSUESUITE_INDEX_MIRROR")
    mirror_path = Path(mirror_env) if mirror_env else None
    persist_index_document(index_path, IndexDocument(entries=entries), mirror=mirror_path)


def _merge_index_mapping(
    index_mapping: dict[str, int],
    latest_mapping: dict[str, int],
    current_slugs: set[str],
) -> dict[str, int]:
    merged = dict(index_mapping)
    if merged and current_slugs:
        _prune_stale_entries(merged, current_slugs)
    if latest_mapping:
        merged.update(latest_mapping)
    return merged


def _prepare_mapping(
    cfg: SuiteConfig,
    summary_raw: dict[str, Any],
    *,
    effective_dry_run: bool,
    mapping_path: str | None,
) -> dict[str, int]:
    existing_mapping = _load_index_mapping(cfg)
    latest_mapping_raw = summary_raw.get("mapping")
    latest_mapping = (
        _normalize_mapping(
            latest_mapping_raw,
            context="summary.mapping",
            value_getter=lambda value: value,
        )
        if isinstance(latest_mapping_raw, dict)
        else {}
    )
    merged_mapping = _merge_index_mapping(
        existing_mapping, latest_mapping, set(latest_mapping.keys())
    )
    if not effective_dry_run and merged_mapping:
        _persist_mapping(cfg, merged_mapping, mapping_path=mapping_path)
    return merged_mapping


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

    merged_mapping = _prepare_mapping(
        cfg,
        summary_raw,
        effective_dry_run=effective_dry_run,
        mapping_path=mapping_path,
    )

    _truncate_body_diffs(summary_raw, cfg.truncate_body_diff)

    # summary_raw is a plain dict produced by IssueSuite.sync; selective unpack
    # Note: dynamic dict assembly; rely on runtime shape not strict static typing here.
    plan_value = summary_raw.get("plan")
    plan_data = cast(
        list[dict[str, Any]] | None,
        plan_value if isinstance(plan_value, list) else None,
    )
    enriched = cast(
        EnrichedSummary,
        {
            "schemaVersion": cfg.schema_version,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dry_run": effective_dry_run,
            "ai_mode": ai_mode,
            "mapping_present": bool(merged_mapping),
            "mapping_size": len(merged_mapping),
            "totals": summary_raw.get("totals", {}),
            "changes": summary_raw.get("changes", {}),
            "mapping": summary_raw.get("mapping", {}),
            **({"plan": plan_data} if plan_data is not None else {}),
        },
    )
    if merged_mapping and len(merged_mapping) <= MAPPING_SNAPSHOT_THRESHOLD:
        enriched["mapping_snapshot"] = dict(merged_mapping)

    # Attach last error if surfaced by suite (only populated on failure path, so none on success)
    if getattr(suite, "_last_error", None):  # attribute is best-effort internal
        le = suite._last_error  # may be None
        if isinstance(le, dict):
            enriched["last_error"] = le
    sp = Path(summary_path or cfg.summary_json)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(enriched, indent=2) + "\n")
    return enriched
