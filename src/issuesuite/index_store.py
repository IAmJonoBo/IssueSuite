from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .github_rest import compute_signature

logger = logging.getLogger(__name__)


@dataclass
class IndexDocument:
    entries: dict[str, dict[str, Any]]
    repo: str | None = None
    version: int = 1
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signature: str = ""

    def ensure_signature(self) -> None:
        self.signature = compute_signature(self.entries)


def persist_index_document(path: Path, document: IndexDocument, mirror: Path | None = None) -> None:
    document.ensure_signature()
    mapping_snapshot: dict[str, int] = {}
    for slug, payload in document.entries.items():
        if isinstance(payload, dict) and "issue" in payload:
            issue_value = payload.get("issue")
            if issue_value is None:
                continue
            try:
                mapping_snapshot[str(slug)] = int(issue_value)
            except (TypeError, ValueError):  # pragma: no cover - defensive coercion
                logger.debug("skipping non-integer mapping for %s: %r", slug, issue_value)
    payload = {
        "version": document.version,
        "generated_at": document.generated_at,
        "repo": document.repo,
        "entries": document.entries,
        "signature": document.signature,
    }
    if mapping_snapshot:
        payload["mapping"] = mapping_snapshot
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    if mirror:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _coerce_entries(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    entries_raw = raw.get("entries")
    if isinstance(entries_raw, dict):
        for slug, payload in entries_raw.items():
            if isinstance(payload, dict):
                sanitized: dict[str, Any] = {str(k): v for k, v in payload.items()}
                entries[str(slug)] = sanitized
    if entries:
        return entries
    mapping_raw = raw.get("mapping")
    if isinstance(mapping_raw, dict):
        for slug, value in mapping_raw.items():
            entries[str(slug)] = {"issue": value}
    return entries


def load_index_document(path: Path) -> IndexDocument:
    if not path.exists():
        return IndexDocument(entries={})
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - IO errors
        logger.debug("Failed to read index document %s: %s", path, exc)
        return IndexDocument(entries={})
    if not isinstance(raw, dict):
        return IndexDocument(entries={})
    entries = _coerce_entries(raw)
    if not entries:
        mapping_raw = raw.get("mapping")
        if isinstance(mapping_raw, dict):
            for slug, value in mapping_raw.items():
                entries[str(slug)] = {"issue": value}

    doc = IndexDocument(
        entries=entries,
        repo=raw.get("repo") if isinstance(raw.get("repo"), str) else None,
        version=int(raw.get("version") or 1),
        generated_at=str(raw.get("generated_at") or datetime.now(timezone.utc).isoformat()),
        signature=str(raw.get("signature") or ""),
    )
    if doc.signature and doc.signature != compute_signature(doc.entries):
        logger.warning("Index signature mismatch detected at %s; ignoring entries", path)
        return IndexDocument(entries={}, repo=doc.repo, version=doc.version)
    return doc


__all__ = ["IndexDocument", "persist_index_document", "load_index_document"]
