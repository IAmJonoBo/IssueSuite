"""Lightweight telemetry sink (opt-in)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from issuesuite.config import SuiteConfig

DEFAULT_FILENAME = "telemetry.jsonl"
DEFAULT_DIRNAME = ".issuesuite"


@dataclass(frozen=True)
class TelemetryConfig:
    enabled: bool
    store_path: Path


def _environment_enabled() -> bool | None:
    flag = os.environ.get("ISSUESUITE_TELEMETRY")
    if flag is None:
        return None
    return flag == "1"


def _environment_store_path(default_path: Path) -> Path:
    override = os.environ.get("ISSUESUITE_TELEMETRY_PATH")
    if not override:
        return default_path
    override_path = Path(override)
    return (
        override_path
        if override_path.is_absolute()
        else default_path.with_name(override_path.name)
    )


def resolve_config(cfg: SuiteConfig | None) -> TelemetryConfig:
    env_override = _environment_enabled()
    enabled = (
        env_override
        if env_override is not None
        else bool(cfg and cfg.telemetry_enabled)
    )
    base_path = (
        Path(cfg.telemetry_store_path)
        if cfg and cfg.telemetry_store_path
        else Path.home() / DEFAULT_DIRNAME / DEFAULT_FILENAME
    )
    store_path = _environment_store_path(base_path)
    return TelemetryConfig(enabled=enabled, store_path=store_path)


def emit(
    cfg: SuiteConfig | None,
    command: str,
    exit_code: int,
    duration_seconds: float,
) -> None:
    config = resolve_config(cfg)
    if not config.enabled:
        return
    payload: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": command,
        "exit_code": int(exit_code),
        "duration_ms": int(duration_seconds * 1000),
        "pid": os.getpid(),
        "version": getattr(__import__("issuesuite"), "__version__", "unknown"),
    }
    try:
        config.store_path.parent.mkdir(parents=True, exist_ok=True)
        with config.store_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    except Exception:  # pragma: no cover - telemetry must never break CLI
        return
