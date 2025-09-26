from __future__ import annotations

"""High-level orchestration utilities bridging legacy script CLI and library.

This module centralizes sync behavior (hash state + mapping + summary JSON)
so the top-level `scripts/issue_suite.py` can delegate instead of duplicating
logic. It intentionally mirrors existing summary JSON shape.
"""

import json
import os
from collections.abc import MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import SuiteConfig
from .core import IssueSuite


def sync_with_summary(
    cfg: SuiteConfig,
    *,
    dry_run: bool,
    update: bool,
    respect_status: bool,
    preflight: bool,
    summary_path: str | None = None,
    mapping_path: str | None = None,
) -> dict[str, Any]:
    """Run a sync using IssueSuite and emit mapping/state + summary JSON.

    Returns the summary dict (same shape used previously by script).
    """
    suite = IssueSuite(cfg)
    ai_mode = os.environ.get("ISSUESUITE_AI_MODE") == "1"
    # In AI mode we always force dry-run to guarantee side-effect free operation for tooling
    effective_dry_run = True if ai_mode else dry_run
    # Run underlying sync to get base summary (without body diffs standardized)
    summary = suite.sync(
        dry_run=effective_dry_run,
        update=update,
        respect_status=respect_status,
        preflight=preflight,
    )

    # Ensure any updated/created items have truncated diffs per config (if present)
    truncate = cfg.truncate_body_diff
    for updated in summary.get("changes", {}).get("updated", []):
        diff_obj: MutableMapping[str, Any] = updated.get("diff") or {}
        body_diff = diff_obj.get("body_diff")
        if isinstance(body_diff, list):  # refine type
            bd_list: list[str] = [str(x) for x in body_diff]
            if truncate and len(bd_list) > truncate:
                updated["diff"]["body_diff"] = bd_list[:truncate] + ["... (truncated)"]

    # Persist mapping if provided by core sync (external_id -> issue number)
    if not dry_run:
        mapping: dict[str, int] = summary.get("mapping", {}) or {}
        mp = Path(mapping_path or cfg.mapping_file)
        mp.write_text(json.dumps(mapping, indent=2) + "\n")

    # augment summary with schemaVersion & timestamp to align with script format
    summary_enriched: dict[str, Any] = {
        "schemaVersion": cfg.schema_version,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": effective_dry_run,
        "ai_mode": ai_mode,
        **summary,
    }

    sp = Path(summary_path or cfg.summary_json)
    sp.write_text(json.dumps(summary_enriched, indent=2) + "\n")
    return summary_enriched
