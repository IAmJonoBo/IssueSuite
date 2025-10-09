"""Centralized retry / backoff helpers.

Provides a single small function ``run_with_retries`` that encapsulates
exponential backoff with jitter and simple classification of transient
GitHub CLI failure modes (rate limit / abuse / secondary rate limits).

Environment overrides:
  ISSUESUITE_RETRY_ATTEMPTS (default 3)
  ISSUESUITE_RETRY_BASE (seconds base, default 0.5)

The caller supplies a thunk returning the desired result or raising
``subprocess.CalledProcessError`` (or generic Exception). Only specific
error messages trigger a retry; other failures propagate immediately.
"""

from __future__ import annotations

import os
import random
import re
import subprocess  # nosec B404 - required for retrying GitHub CLI interactions
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

TRANSIENT_TOKENS = (
    "rate limit",
    "abuse detection",
    "secondary rate",
)

_RE_RETRY_AFTER = re.compile(r"retry[-\s]after:?\s*(\d+)", re.IGNORECASE)
_RE_SECONDS_HINT = re.compile(r"wait\s*(\d+)\s*seconds", re.IGNORECASE)
_JITTER = random.SystemRandom()


def _extract_explicit_backoff(text: str) -> float | None:
    """Extract an explicit backoff (seconds) from error output.

    Supports patterns like:
      Retry-After: 12
      retry after 12
      wait 30 seconds
    Returns None if no valid positive value found.
    """
    if not text:
        return None
    m = _RE_RETRY_AFTER.search(text)
    if m:
        try:
            val = float(m.group(1))
            return val if val > 0 else None
        except ValueError:  # pragma: no cover - defensive
            return None
    m2 = _RE_SECONDS_HINT.search(text)
    if m2:
        try:
            val = float(m2.group(1))
            return val if val > 0 else None
        except ValueError:  # pragma: no cover
            return None
    return None


@dataclass
class RetryConfig:
    attempts: int = int(os.environ.get("ISSUESUITE_RETRY_ATTEMPTS", "3"))
    base_sleep: float = float(os.environ.get("ISSUESUITE_RETRY_BASE", "0.5"))


def is_transient(output: str) -> bool:
    out_lower = output.lower()
    return any(tok in out_lower for tok in TRANSIENT_TOKENS)


def _compute_sleep(attempt: int, cfg: RetryConfig, out: str) -> float:
    explicit = _extract_explicit_backoff(out)
    backoff = cfg.base_sleep * (2 ** (attempt - 1)) + _JITTER.uniform(0, 0.25)
    sleep_for: float = explicit if explicit is not None else backoff
    max_cap_env = os.environ.get("ISSUESUITE_RETRY_MAX_SLEEP")
    if max_cap_env:
        try:
            cap = float(max_cap_env)
            if cap >= 0:
                sleep_for = min(sleep_for, cap)
        except ValueError:  # pragma: no cover
            return sleep_for
    return sleep_for


def _handle_called_process_error(
    exc: subprocess.CalledProcessError, attempt: int, attempts: int, cfg: RetryConfig
) -> bool:
    out = exc.output or ""
    if attempt >= attempts or not is_transient(out):
        return False
    sleep_for = _compute_sleep(attempt, cfg, out)
    print(f"[retry] transient error, attempt {attempt}/{attempts}, sleeping {sleep_for:.2f}s")
    time.sleep(sleep_for)
    return True


def run_with_retries(fn: Callable[[], T], *, cfg: RetryConfig | None = None) -> T:
    cfg = cfg or RetryConfig()
    attempts = max(1, cfg.attempts)
    for attempt in range(1, attempts + 1):  # noqa: PLR2004
        try:
            return fn()
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            if not _handle_called_process_error(exc, attempt, attempts, cfg):
                raise
    raise RuntimeError("retry logic exited unexpectedly")  # pragma: no cover


__all__ = ["RetryConfig", "run_with_retries", "is_transient"]
