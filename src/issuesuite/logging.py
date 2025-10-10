"""Structured JSON logging for IssueSuite (clean minimal version)."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Known structured attributes
        for attr in (
            "operation",
            "external_id",
            "issue_number",
            "duration_ms",
            "dry_run",
            "error",
            "slug",
        ):
            if hasattr(record, attr):  # pragma: no cover
                entry[attr] = getattr(record, attr)
        # Pass through arbitrary extra kwargs (those we injected) while filtering noisy internals
        allowed_extras = {"param1", "param2", "spec_count"}  # extend as needed
        for k, v in record.__dict__.items():  # pragma: no cover - dynamic filtering
            if k in allowed_extras:
                entry[k] = v
        # Include any extra (non-standard) attributes passed via extra kwargs
        reserved = set(entry.keys()) | {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "lineno",
        }
        for k, v in record.__dict__.items():
            if k not in reserved and not k.startswith("_") and k not in entry:
                entry[k] = v
        return json.dumps(entry)


class StructuredLogger:
    def __init__(
        self, name: str = "issuesuite", json_logging: bool = False, level: str = "INFO"
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        for h in self._logger.handlers:
            self._logger.removeHandler(h)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            JSONFormatter()
            if json_logging
            else logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        self._logger.addHandler(handler)
        self._logger.propagate = False
        self._dedupe_enabled = json_logging
        self._last_signature: tuple[int, str, tuple[tuple[str, str], ...]] | None = None

    def _emit(self, level: int, message: str, extra: dict[str, Any]) -> None:
        if self._dedupe_enabled:
            signature = (
                level,
                message,
                tuple(sorted((k, repr(v)) for k, v in extra.items())),
            )
            if signature == self._last_signature:
                return
            self._last_signature = signature
        self._logger.log(level, message, extra=extra)

    def log_operation(self, operation: str, **kw: Any) -> None:
        # Maintain legacy message format validated by tests
        extra = {"operation": operation, **kw}
        self._emit(logging.INFO, f"Operation: {operation}", extra)

    def log_issue_action(
        self,
        action: str,
        external_id: str,
        issue_number: int | None = None,
        dry_run: bool = False,
        **kw: Any,
    ) -> None:
        extra: dict[str, Any] = {
            "operation": f"issue_{action}",
            "external_id": external_id,
            "dry_run": dry_run,
            "slug": external_id,
            **kw,
        }
        if issue_number:
            extra["issue_number"] = issue_number
        msg = (
            f"issue {action} {external_id}"
            + (f" #{issue_number}" if issue_number else "")
            + (" [DRY]" if dry_run else "")
        )
        self._emit(logging.INFO, msg, extra)

    def log_performance(self, operation: str, duration_ms: float, **kw: Any) -> None:
        extra = {"operation": operation, "duration_ms": round(duration_ms, 2), **kw}
        self._emit(
            logging.INFO,
            f"Performance: {operation} completed in {duration_ms:.2f}ms",
            extra,
        )

    def log_error(self, message: str, error: str | None = None, **kw: Any) -> None:
        extra = dict(kw)
        if error:
            extra["error"] = error
        self._logger.error(message, extra=extra)

    def debug(self, message: str, **kw: Any) -> None:
        self._logger.debug(message, extra=kw)

    def info(self, message: str, **kw: Any) -> None:
        self._logger.info(message, extra=kw)

    def warning(self, message: str, **kw: Any) -> None:
        self._logger.warning(message, extra=kw)

    def error(self, message: str, **kw: Any) -> None:  # noqa: D401
        self._logger.error(message, extra=kw)

    def log_type_check_metrics(self, report_path: Path | None = None) -> None:
        candidates: list[Path] = []
        if report_path is not None:
            candidates.append(report_path)
        else:
            candidates.append(Path.cwd() / "type_coverage.json")
            candidates.append(Path(__file__).resolve().parents[2] / "type_coverage.json")
        for candidate in candidates:
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except FileNotFoundError:
                continue
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                self.warning(
                    "type coverage telemetry invalid",
                    report=str(candidate),
                    error=str(exc),
                )
                return
            modules_total = data.get("modules_total")
            strict_clean = data.get("modules_strict_clean")
            strict_ratio = data.get("strict_ratio")
            payload = {
                "operation": "type_check",
                "modules_total": modules_total,
                "modules_strict_clean": strict_clean,
                "strict_ratio": strict_ratio,
                "report_path": str(candidate),
            }
            self._emit(logging.INFO, "Type coverage snapshot", payload)
            return
        self.debug("type coverage report not found", report="type_coverage.json")

    @contextmanager
    def timed_operation(self, operation: str, **kw: Any) -> Iterator[None]:  # noqa: D401
        start = time.perf_counter()
        self.log_operation(f"{operation}_start", **kw)
        try:
            yield
            self.log_performance(operation, (time.perf_counter() - start) * 1000, **kw)
        except Exception as exc:  # pragma: no cover
            self.log_error(f"operation {operation} failed", error=str(exc), **kw)
            raise


_GLOBAL: StructuredLogger | None = None


def get_logger() -> StructuredLogger:
    global _GLOBAL  # noqa: PLW0603
    if _GLOBAL is None:
        _GLOBAL = StructuredLogger()
    return _GLOBAL


def configure_logging(json_logging: bool = False, level: str = "INFO") -> StructuredLogger:
    global _GLOBAL  # noqa: PLW0603
    _GLOBAL = StructuredLogger(json_logging=json_logging, level=level)
    try:
        _GLOBAL.log_type_check_metrics()
    except Exception:  # pragma: no cover - telemetry should never crash configuration
        _GLOBAL.debug("type coverage telemetry emission failed")
    return _GLOBAL
