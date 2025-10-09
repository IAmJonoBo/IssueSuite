"""Coverage trend utilities for GitHub Projects telemetry."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

DEFAULT_TARGET = 0.85
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = PROJECT_ROOT / "coverage_summary.json"
HISTORY_PATH = PROJECT_ROOT / "coverage_trends.json"
SNAPSHOT_PATH = PROJECT_ROOT / "coverage_trends_latest.json"
PROJECT_PAYLOAD_PATH = PROJECT_ROOT / "coverage_projects_payload.json"


class CoverageTrendError(RuntimeError):
    """Raised when coverage telemetry cannot be parsed."""


@dataclass(frozen=True)
class ModuleTrend:
    module: str
    coverage: float | None
    threshold: float | None
    meets_threshold: bool
    delta: float | None
    trend: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "coverage": self.coverage,
            "threshold": self.threshold,
            "meets_threshold": self.meets_threshold,
            "delta": self.delta,
            "trend": self.trend,
        }


def _ensure_modules(summary: dict[str, Any]) -> Sequence[dict[str, Any]]:
    modules = summary.get("modules")
    if not isinstance(modules, Sequence):
        raise CoverageTrendError("coverage_summary.json missing modules array")
    return modules


def _load_summary(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists():
        raise CoverageTrendError(f"coverage summary not found: {summary_path}")
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid file surface to caller
        raise CoverageTrendError(f"invalid coverage summary: {exc}") from exc
    if not isinstance(data, dict):
        raise CoverageTrendError("coverage summary must be a JSON object")
    return cast(dict[str, Any], data)


def _load_history(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    text = history_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid file surface to caller
        raise CoverageTrendError(f"invalid coverage trend history: {exc}") from exc
    if not isinstance(data, list):
        raise CoverageTrendError("coverage trend history must be a list")
    history: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise CoverageTrendError("coverage trend history entries must be objects")
        history.append(cast(dict[str, Any], entry))
    return history


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _compute_overall(modules: Iterable[ModuleTrend]) -> float | None:
    values = [module.coverage for module in modules if module.coverage is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _compute_delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def _previous_module_map(previous: dict[str, Any] | None) -> dict[str, ModuleTrend]:
    if not previous:
        return {}
    modules = previous.get("modules", [])
    result: dict[str, ModuleTrend] = {}
    for module in modules:
        name = module.get("module")
        if not isinstance(name, str):
            continue
        result[name] = ModuleTrend(
            module=name,
            coverage=_to_float(module.get("coverage")),
            threshold=_to_float(module.get("threshold")),
            meets_threshold=bool(module.get("meets_threshold", False)),
            delta=_to_float(module.get("delta")),
            trend=str(module.get("trend", "steady")),
        )
    return result


def build_trend_entry(
    summary: dict[str, Any],
    *,
    recorded_at: datetime,
    target: float = DEFAULT_TARGET,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    modules_payload = _ensure_modules(summary)
    previous_map = _previous_module_map(previous)
    module_trends: list[ModuleTrend] = []
    regressions: list[str] = []
    improvements: list[str] = []

    for module_payload in modules_payload:
        module_name = module_payload.get("module")
        if not isinstance(module_name, str):
            continue
        coverage = _to_float(module_payload.get("coverage"))
        threshold = _to_float(module_payload.get("threshold"))
        meets_threshold = bool(module_payload.get("meets_threshold", False))
        previous_entry = previous_map.get(module_name)
        delta = _compute_delta(coverage, previous_entry.coverage if previous_entry else None)
        trend = "steady"
        if delta is not None:
            if delta > 0:
                improvements.append(module_name)
                trend = "improved"
            elif delta < 0:
                regressions.append(module_name)
                trend = "regressed"
        module_trends.append(
            ModuleTrend(
                module=module_name,
                coverage=coverage,
                threshold=threshold,
                meets_threshold=meets_threshold,
                delta=delta,
                trend=trend,
            )
        )

    overall = _compute_overall(module_trends)
    previous_overall = None
    if previous and isinstance(previous.get("overall"), dict):
        previous_overall = _to_float(previous["overall"].get("coverage"))
    overall_delta = _compute_delta(overall, previous_overall)

    entry = {
        "recorded_at": recorded_at.isoformat(),
        "summary_generated_at": summary.get("generated_at"),
        "overall": {
            "coverage": overall,
            "target": target,
            "meets_target": overall is not None and overall >= target,
            "delta": overall_delta,
        },
        "modules": [trend.to_dict() for trend in module_trends],
        "regressions": regressions,
        "improvements": improvements,
    }
    return entry


def _build_project_payload(entry: dict[str, Any]) -> dict[str, Any]:
    overall = entry.get("overall", {})
    coverage = _to_float(overall.get("coverage"))
    target = _to_float(overall.get("target")) or DEFAULT_TARGET
    failing_modules = [
        module["module"]
        for module in entry.get("modules", [])
        if not module.get("meets_threshold", False)
    ]
    regressions = list(entry.get("regressions", []))
    improvements = list(entry.get("improvements", []))

    status = "on_track"
    if failing_modules:
        status = "off_track"
    elif regressions:
        status = "at_risk"

    emoji = {"on_track": "✅", "at_risk": "⚠️", "off_track": "❌"}[status]
    coverage_display = f"{coverage * 100:.2f}%" if coverage is not None else "n/a"
    target_display = f"{target * 100:.0f}%"
    summary_lines = [f"Overall coverage {coverage_display} (target {target_display})"]
    if failing_modules:
        summary_lines.append("Modules below threshold: " + ", ".join(failing_modules))
    if regressions:
        summary_lines.append("Regressions: " + ", ".join(regressions))
    if improvements:
        summary_lines.append("Improvements: " + ", ".join(improvements))

    return {
        "status": status,
        "emoji": emoji,
        "overall_coverage": coverage,
        "target": target,
        "delta": overall.get("delta"),
        "failing_modules": failing_modules,
        "regressions": regressions,
        "improvements": improvements,
        "message": " | ".join(summary_lines),
        "recorded_at": entry.get("recorded_at"),
    }


def export_trends(
    *,
    summary_path: Path = SUMMARY_PATH,
    history_path: Path = HISTORY_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
    project_payload_path: Path = PROJECT_PAYLOAD_PATH,
    max_records: int = 200,
    now: datetime | None = None,
    target: float = DEFAULT_TARGET,
) -> dict[str, Any]:
    summary = _load_summary(summary_path)
    history = _load_history(history_path)
    previous = history[-1] if history else None
    timestamp = now or datetime.now(tz=timezone.utc)
    entry = build_trend_entry(summary, recorded_at=timestamp, target=target, previous=previous)

    history.append(entry)
    if max_records > 0 and len(history) > max_records:
        history = history[-max_records:]

    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    snapshot_path.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")

    project_payload = _build_project_payload(entry)
    project_payload_path.write_text(json.dumps(project_payload, indent=2) + "\n", encoding="utf-8")
    return entry


__all__ = [
    "CoverageTrendError",
    "ModuleTrend",
    "build_trend_entry",
    "export_trends",
]
