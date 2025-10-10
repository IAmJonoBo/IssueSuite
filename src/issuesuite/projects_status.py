from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .coverage_trends import PROJECT_PAYLOAD_PATH
from .next_steps_validator import DEFAULT_FILES

TASK_CHECKBOX = re.compile(r"^- \[(?P<state>[ xX])\]\s*(?P<body>.+)")
OWNER_PATTERN = re.compile(
    r"\*\*Owner:\*\*\s*(?P<owner>[^()\u2014\-]+?)(?:\s*\(Due:\s*(?P<due>\d{4}-\d{2}-\d{2})\))?\s*[\u2014-]\s*(?P<description>.+)",
    re.IGNORECASE,
)
DEFAULT_LOOKAHEAD_DAYS = 7


@dataclass(frozen=True)
class TaskEntry:
    raw: str
    completed: bool
    owner: str | None
    due: date | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "owner": self.owner,
            "due": self.due.isoformat() if self.due else None,
            "description": self.description,
        }


class ProjectsStatusError(RuntimeError):
    """Raised when the projects status report cannot be generated."""


def _extract_tasks_section(text: str) -> str:
    marker = "## Tasks"
    start = text.find(marker)
    if start == -1:
        return ""
    start = text.find("\n", start)
    if start == -1:
        return ""
    end = text.find("\n## ", start + 1)
    if end == -1:
        end = len(text)
    return text[start:end]


def _parse_line(line: str) -> TaskEntry | None:
    match = TASK_CHECKBOX.match(line.strip())
    if not match:
        return None
    body = match.group("body").strip()
    completed = match.group("state").lower() == "x"
    owner = None
    due_value: date | None = None
    description = body

    owner_match = OWNER_PATTERN.match(body)
    if owner_match:
        owner = owner_match.group("owner")
        if owner:
            owner = owner.strip()
        due_str = owner_match.group("due")
        if due_str:
            try:
                due_value = datetime.strptime(due_str, "%Y-%m-%d").date()
            except ValueError:
                due_value = None
        description = owner_match.group("description").strip()
    else:
        # Fallback: attempt to split on em dash or hyphen
        for separator in (" — ", " - "):
            if separator in body:
                before, after = body.split(separator, 1)
                owner = before.strip() or None
                description = after.strip()
                break

    return TaskEntry(
        raw=line,
        completed=completed,
        owner=owner,
        due=due_value,
        description=description,
    )


def parse_tasks(section: str) -> list[TaskEntry]:
    tasks: list[TaskEntry] = []
    for line in section.splitlines():
        entry = _parse_line(line)
        if entry:
            tasks.append(entry)
    return tasks


def summarize_tasks(
    tasks: Sequence[TaskEntry],
    *,
    now: date | None = None,
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> dict[str, Any]:
    today = now or datetime.now(tz=timezone.utc).date()
    window_end = today + timedelta(days=max(lookahead_days, 0))

    total = len(tasks)
    open_count = 0
    completed_count = 0
    overdue: list[TaskEntry] = []
    due_soon: list[TaskEntry] = []

    for task in tasks:
        if task.completed:
            completed_count += 1
            continue
        open_count += 1
        if task.due:
            if task.due < today:
                overdue.append(task)
            elif today <= task.due <= window_end:
                due_soon.append(task)

    return {
        "entries": list(tasks),
        "total_count": total,
        "open_count": open_count,
        "completed_count": completed_count,
        "overdue_count": len(overdue),
        "due_soon_count": len(due_soon),
        "overdue": overdue,
        "due_soon": due_soon,
    }


def _load_next_steps(paths: Sequence[Path] | None = None) -> str:
    candidates: Iterable[Path]
    if paths:
        candidates = paths
    else:
        candidates = DEFAULT_FILES
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise ProjectsStatusError(
        "No Next Steps file found; expected one of: "
        + ", ".join(str(p) for p in DEFAULT_FILES)
    )


def load_coverage_payload(path: Path | None = None) -> dict[str, Any] | None:
    payload_path = path or PROJECT_PAYLOAD_PATH
    if not payload_path.exists():
        return None
    try:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
    except (
        json.JSONDecodeError
    ) as exc:  # pragma: no cover - invalid file surfaces to caller
        raise ProjectsStatusError(f"Invalid coverage payload: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectsStatusError("Coverage payload must be a JSON object")
    return data


def combine_status(
    coverage: dict[str, Any] | None, summary: dict[str, Any]
) -> dict[str, Any]:
    base_status = "on_track"
    coverage_message = (
        "Coverage data unavailable; run scripts/coverage_trends.py before reporting."
    )
    emoji_map = {"on_track": "✅", "at_risk": "⚠️", "off_track": "❌"}

    if coverage:
        candidate_status = str(coverage.get("status") or "on_track").lower()
        if candidate_status in emoji_map:
            base_status = candidate_status
        coverage_message = str(coverage.get("message") or coverage_message)
    status = base_status

    if summary.get("overdue_count", 0) > 0:
        status = "off_track"
    elif summary.get("due_soon_count", 0) > 0 and status == "on_track":
        status = "at_risk"

    emoji = emoji_map.get(status, emoji_map[base_status])
    message_parts = [coverage_message]
    overdue_count = summary.get("overdue_count", 0)
    due_soon_count = summary.get("due_soon_count", 0)
    open_count = summary.get("open_count", 0)
    total_count = summary.get("total_count", 0)

    if overdue_count:
        label = "task" if overdue_count == 1 else "tasks"
        message_parts.append(f"{overdue_count} overdue {label}")
    if due_soon_count:
        label = "task" if due_soon_count == 1 else "tasks"
        message_parts.append(f"{due_soon_count} due within the lookahead window")
    if open_count == 0 and total_count:
        message_parts.append("All tracked tasks complete")

    return {
        "status": status,
        "emoji": emoji,
        "message": " | ".join(message_parts),
        "coverage_message": coverage_message,
    }


def generate_report(
    *,
    next_steps_paths: Sequence[Path] | None = None,
    coverage_payload_path: Path | None = None,
    now: datetime | None = None,
    lookahead_days: int | None = DEFAULT_LOOKAHEAD_DAYS,
) -> dict[str, Any]:
    timestamp = now or datetime.now(tz=timezone.utc)
    next_steps_text = _load_next_steps(next_steps_paths)
    tasks_section = _extract_tasks_section(next_steps_text)
    tasks = parse_tasks(tasks_section)
    effective_lookahead = (
        DEFAULT_LOOKAHEAD_DAYS if lookahead_days is None else lookahead_days
    )
    summary = summarize_tasks(
        tasks, now=timestamp.date(), lookahead_days=effective_lookahead
    )
    coverage = load_coverage_payload(coverage_payload_path)
    status_payload = combine_status(coverage, summary)

    report = {
        "generated_at": timestamp.isoformat(),
        "status": status_payload["status"],
        "emoji": status_payload["emoji"],
        "message": status_payload["message"],
        "coverage": coverage or {},
        "coverage_message": status_payload["coverage_message"],
        "tasks": summary,
        "lookahead_days": effective_lookahead,
    }
    return report


def _format_task(task: TaskEntry) -> str:
    owner = task.owner or "Unassigned"
    due = f" (due {task.due.isoformat()})" if task.due else ""
    return f"{owner} — {task.description}{due}"


def render_comment(report: dict[str, Any]) -> str:
    emoji = report.get("emoji", "⚠️")
    status = str(report.get("status", "at_risk")).replace("_", " ").title()
    coverage_message = report.get("coverage_message") or report.get("coverage", {}).get(
        "message"
    )
    tasks = report.get("tasks", {})

    lines = [f"{emoji} Frontier Apex status: {status}"]
    if coverage_message:
        lines.append(f"- Coverage: {coverage_message}")
    lines.append(
        f"- Tasks open: {tasks.get('open_count', 0)} of {tasks.get('total_count', 0)} | "
        f"Overdue: {tasks.get('overdue_count', 0)} | Due soon: {tasks.get('due_soon_count', 0)}"
    )

    overdue_tasks = tasks.get("overdue") or []
    if overdue_tasks:
        lines.append("- Overdue:")
        for task in overdue_tasks:
            lines.append(f"  • {_format_task(task)}")
    due_soon_tasks = tasks.get("due_soon") or []
    if due_soon_tasks:
        lines.append("- Due soon:")
        for task in due_soon_tasks:
            lines.append(f"  • {_format_task(task)}")

    return "\n".join(lines)


def serialize_report(report: dict[str, Any]) -> dict[str, Any]:
    tasks = report.get("tasks", {})
    serialized_tasks = {**tasks}
    for key in ("entries", "overdue", "due_soon"):
        if key in serialized_tasks:
            serialized_tasks[key] = [task.to_dict() for task in serialized_tasks[key]]
    payload = {**report, "tasks": serialized_tasks}
    return payload


__all__ = [
    "TaskEntry",
    "ProjectsStatusError",
    "parse_tasks",
    "summarize_tasks",
    "load_coverage_payload",
    "combine_status",
    "generate_report",
    "render_comment",
    "serialize_report",
]
