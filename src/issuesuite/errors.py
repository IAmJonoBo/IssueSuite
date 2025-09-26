"""Error taxonomy & redaction scaffolding.

This module introduces a lightweight, extensible structure for classifying
errors and preparing them for safe logging / reporting. Current implementation
is intentionally minimal; future iterations can expand token detection,
layer-specific categories, and integration with orchestrator summaries.

Public API (initial):
- classify_error(exc) -> ErrorInfo
- redact(text) -> str

Usage goals:
- Central place to evolve error categories without scattering conditionals.
- Provide redaction for sensitive substrings (tokens, file paths, possibly emails).
- Allow future mapping to metrics / schema exports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Simple token patterns; can be expanded (e.g., GitHub token, private key markers)
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ghp_[A-Za-z0-9]{20,40}"),  # GitHub classic tokens
    re.compile(r"github_pat_\w{20,}"),  # GitHub fine-grained tokens
    re.compile(r"-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----"),
]

_REDACTION_PLACEHOLDER = "<redacted>"


@dataclass
class ErrorInfo:
    category: str
    message: str
    original_type: str
    transient: bool = False
    details: dict[str, Any] | None = None


def redact(text: str) -> str:
    """Redact sensitive tokens in arbitrary text.

    Current approach: replace pattern matches with a placeholder. Future
    improvement: partial masking (prefix/suffix reveal) & streaming redaction.
    """
    if not text:
        return text
    redacted = text
    for pat in _SENSITIVE_PATTERNS:
        redacted = pat.sub(_REDACTION_PLACEHOLDER, redacted)
    return redacted


def classify_error(exc: BaseException) -> ErrorInfo:
    """Best-effort classification of an exception.

    Strategy (initial minimal taxonomy):
    - Subprocess errors referencing rate limits -> category 'github.rate_limit', transient True
    - Network-y keywords -> category 'network', transient True
    - YAML / parse errors -> category 'parse'
    - Fallback -> 'generic'
    """
    msg = str(exc) if exc else ""
    low = msg.lower()

    if "rate limit" in low or "secondary rate" in low:
        return ErrorInfo("github.rate_limit", redact(msg), exc.__class__.__name__, transient=True)
    if "abuse" in low:
        return ErrorInfo("github.abuse", redact(msg), exc.__class__.__name__, transient=True)
    if any(k in low for k in ("timeout", "connection reset", "temporarily unavailable")):
        return ErrorInfo("network", redact(msg), exc.__class__.__name__, transient=True)
    if any(k in low for k in ("yaml", "scannererror", "parsererror")):
        return ErrorInfo("parse", redact(msg), exc.__class__.__name__)
    return ErrorInfo("generic", redact(msg), exc.__class__.__name__)


__all__ = ["ErrorInfo", "classify_error", "redact"]
