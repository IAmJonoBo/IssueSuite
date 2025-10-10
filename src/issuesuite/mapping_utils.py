from __future__ import annotations

import logging
from typing import Any

from .config import SuiteConfig
from .index_store import load_index_document

MAPPING_SNAPSHOT_THRESHOLD = 500


logger = logging.getLogger(__name__)


def load_mapping_snapshot(cfg: SuiteConfig) -> dict[str, int]:
    """Best-effort load of mapping snapshot from .issuesuite/index.json.

    Returns empty dict on any error or absence. Values coerced to int when possible.
    """
    idx = cfg.source_file.parent / ".issuesuite" / "index.json"
    doc = load_index_document(idx)
    out: dict[str, int] = {}
    for slug, entry in doc.entries.items():
        issue_value: Any = entry.get("issue") if isinstance(entry, dict) else entry
        try:
            out[str(slug)] = int(issue_value)
        except Exception as exc:
            logger.debug(
                "Skipping non-numeric mapping value %s=%s: %s", slug, entry, exc
            )
    return out


__all__ = [
    "MAPPING_SNAPSHOT_THRESHOLD",
    "load_mapping_snapshot",
]
