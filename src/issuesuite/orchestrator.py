from __future__ import annotations

"""High-level orchestration utilities bridging legacy script CLI and library.

This module centralizes sync behavior (hash state + mapping + summary JSON)
so the top-level `scripts/issue_suite.py` can delegate instead of duplicating
logic. It intentionally mirrors existing summary JSON shape.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
from .config import SuiteConfig
from .core import IssueSuite
import difflib


def sync_with_summary(
    cfg: SuiteConfig,
    *,
    dry_run: bool,
    update: bool,
    respect_status: bool,
    preflight: bool,
    summary_path: Optional[str] = None,
    mapping_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a sync using IssueSuite and emit mapping/state + summary JSON.

    Returns the summary dict (same shape used previously by script).
    """
    suite = IssueSuite(cfg)
    # Run underlying sync to get base summary (without body diffs standardized)
    summary = suite.sync(dry_run=dry_run, update=update, respect_status=respect_status, preflight=preflight)

    # Ensure any updated/created items have truncated diffs per config (if present)
    truncate = cfg.truncate_body_diff
    for updated in summary.get('changes', {}).get('updated', []):
        diff_obj = updated.get('diff') or {}
        body_diff = diff_obj.get('body_diff')
        if isinstance(body_diff, list) and truncate and len(body_diff) > truncate:
            updated['diff']['body_diff'] = body_diff[:truncate] + ['... (truncated)']

    # Persist mapping if provided by core sync (external_id -> issue number)
    if not dry_run:
        mapping = summary.get('mapping', {}) or {}
        mp = Path(mapping_path or cfg.mapping_file)
        mp.write_text(json.dumps(mapping, indent=2) + '\n')

    # augment summary with schemaVersion & timestamp to align with script format
    from datetime import datetime, timezone
    summary_enriched = {
        'schemaVersion': cfg.schema_version,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'dry_run': dry_run,
        **summary,
    }

    sp = Path(summary_path or cfg.summary_json)
    sp.write_text(json.dumps(summary_enriched, indent=2) + '\n')
    return summary_enriched
