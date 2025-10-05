from __future__ import annotations

import json
import logging
from typing import Any

from .config import SuiteConfig

MAPPING_SNAPSHOT_THRESHOLD = 500


logger = logging.getLogger(__name__)


def load_mapping_snapshot(cfg: SuiteConfig) -> dict[str, int]:
    """Best-effort load of mapping snapshot from .issuesuite/index.json.

    Returns empty dict on any error or absence. Values coerced to int when possible.
    """
    idx = cfg.source_file.parent / ".issuesuite" / "index.json"
    if not idx.exists():
        return {}
    try:
        raw: Any = json.loads(idx.read_text())
    except Exception:  # pragma: no cover
        return {}
    if not isinstance(raw, dict):
        return {}
    mapping = raw.get("mapping")
    if not isinstance(mapping, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in mapping.items():
        try:
            out[str(k)] = int(v)  # bools and numeric-like strings will coerce
        except Exception as exc:
            logger.debug("Skipping non-numeric mapping value %s=%s: %s", k, v, exc)
            continue
    return out


__all__ = [
    "MAPPING_SNAPSHOT_THRESHOLD",
    "load_mapping_snapshot",
]
