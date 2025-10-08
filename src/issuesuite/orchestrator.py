"""High-level orchestration utilities bridging legacy script CLI and library.

Centralizes sync behavior (hash state + mapping + summary JSON) while keeping
public API surface minimal. The enriched summary mirrors prior script output
with additional metadata for AI and future reconcile features.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict, cast

from .config import SuiteConfig
from .core import IssueSuite

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
    try:
        raw: Any = json.loads(idx_file.read_text())
    except Exception:
        return {}
    if not isinstance(raw, dict):  # defensive
        return {}
    raw_map: Any = raw.get("mapping")
    if not isinstance(raw_map, dict):
        return {}
    result: dict[str, int] = {}
    for k, v in raw_map.items():
        try:
            result[str(k)] = int(v)  # cast numeric-like values
        except Exception:
            continue
    return result


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
    legacy_mp.write_text(json.dumps(mapping, indent=2) + "\n")
    index_dir = cfg.source_file.parent / ".issuesuite"
    index_dir.mkdir(exist_ok=True)
    (index_dir / "index.json").write_text(json.dumps({"mapping": mapping}, indent=2) + "\n")


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
    index_mapping = _load_index_mapping(cfg)
    latest_mapping_raw = summary_raw.get("mapping")
    latest_mapping: dict[str, int] = {}
    if isinstance(latest_mapping_raw, dict):
        for k, v in latest_mapping_raw.items():
            try:
                latest_mapping[str(k)] = int(v)  # cast numeric-ish
            except Exception:
                continue
    # Determine current slugs (parsed specs count in summary_raw if present or derive from mapping)
    current_slugs: set[str] = set()
    if latest_mapping:
        current_slugs.update(latest_mapping.keys())
    # Prune any stale entries (slugs not present anymore)
    if index_mapping:
        stale = [k for k in index_mapping.keys() if k not in current_slugs and current_slugs]
        if stale:
            for k in stale:
                index_mapping.pop(k, None)
    if latest_mapping:
        index_mapping.update(latest_mapping)

    # Truncate body diffs if configured
    _truncate_body_diffs(summary_raw, cfg.truncate_body_diff)

    # Persist mapping only if not an effective dry-run (write merged/pruned set)
    if not effective_dry_run and index_mapping:
        _persist_mapping(cfg, index_mapping, mapping_path=mapping_path)

    # summary_raw is a plain dict produced by IssueSuite.sync; selective unpack
    # Note: dynamic dict assembly; rely on runtime shape not strict static typing here.
    plan_value = summary_raw.get("plan")
    plan_data = cast(
        list[dict[str, Any]] | None, plan_value if isinstance(plan_value, list) else None
    )
    enriched = cast(
        EnrichedSummary,
        {
            "schemaVersion": cfg.schema_version,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dry_run": effective_dry_run,
            "ai_mode": ai_mode,
            "mapping_present": bool(index_mapping),
            "mapping_size": len(index_mapping),
            "totals": summary_raw.get("totals", {}),
            "changes": summary_raw.get("changes", {}),
            "mapping": summary_raw.get("mapping", {}),
            **({"plan": plan_data} if plan_data is not None else {}),
        },
    )
    if index_mapping and len(index_mapping) <= MAPPING_SNAPSHOT_THRESHOLD:
        enriched["mapping_snapshot"] = dict(index_mapping)

    # Attach last error if surfaced by suite (only populated on failure path, so none on success)
    if getattr(suite, "_last_error", None):  # attribute is best-effort internal
        le = suite._last_error  # may be None
        if isinstance(le, dict):
            enriched["last_error"] = le
    sp = Path(summary_path or cfg.summary_json)
    sp.write_text(json.dumps(enriched, indent=2) + "\n")
    return enriched
