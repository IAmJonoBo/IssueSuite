from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IssueSpec:
    """Canonical in-memory representation of a parsed issue specification.

    This was originally defined inside core.py; extracted for reuse by the
    parser and diffing logic to reduce circular concerns.
    """

    external_id: str  # slug
    title: str
    labels: list[str]
    milestone: str | None
    body: str
    status: str | None = None
    hash: str | None = None
    project: dict[str, Any] | None = None


__all__ = ["IssueSpec"]
