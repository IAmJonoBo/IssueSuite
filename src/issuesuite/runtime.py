"""Runtime helpers for IssueSuite CLI orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from issuesuite import plugins, telemetry
from issuesuite.config import SuiteConfig, load_config


class _HandlerCallable(Protocol):
    def __call__(self) -> Any: ...


def prepare_config(
    args: Any, *, loader: Callable[[str], SuiteConfig] = load_config
) -> SuiteConfig | None:
    """Load and post-process SuiteConfig for the given argparse namespace."""
    if getattr(args, "cmd", None) in {"init", "setup"}:
        return None
    if not hasattr(args, "config"):
        raise AttributeError("Command namespace is missing 'config' attribute")
    cfg = loader(args.config)
    repo_override = getattr(args, "repo", None)
    if repo_override:
        cfg.github_repo = repo_override
    if (
        getattr(args, "cmd", None) == "sync"
        and getattr(args, "project_number", None) is not None
    ):
        try:
            project_number = int(args.project_number)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            project_number = None
        if project_number and project_number > 0:
            cfg.project_number = project_number
            cfg.project_enable = True
    return cfg


def _instrument_command(
    cfg: SuiteConfig | None,
    args: Any,
    command: str,
    exit_code: int,
    start_time: float,
) -> None:
    duration = max(0.0, time.monotonic() - start_time)
    payload: dict[str, Any] = {"args": vars(args), "exit_code": exit_code}
    extra = getattr(args, "_plugin_payload", None)
    if isinstance(extra, dict):
        payload.update(extra)
    plugins.invoke_plugins(cfg, command, payload)
    telemetry.emit(cfg, command, exit_code, duration)


def execute_command(
    handler: _HandlerCallable, args: Any, cfg: SuiteConfig | None, command: str
) -> int:
    """Execute a command handler while emitting telemetry and plugins."""
    start = time.monotonic()
    try:
        result = handler()
        exit_code = int(result) if result is not None else 0
    except SystemExit as exc:  # pragma: no cover - allow propagation
        exit_code = int(exc.code or 0)
        _instrument_command(cfg, args, command, exit_code, start)
        raise
    except Exception:
        exit_code = 1
        _instrument_command(cfg, args, command, exit_code, start)
        raise
    _instrument_command(cfg, args, command, exit_code, start)
    return exit_code


__all__ = ["prepare_config", "execute_command"]
