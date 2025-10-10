from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from issuesuite.projects_status import (
    TaskEntry,
    combine_status,
    generate_report,
    parse_tasks,
    render_comment,
    summarize_tasks,
)


def test_parse_tasks_extracts_metadata() -> None:
    section = (
        "- [x] **Owner:** Assistant (Due: 2025-10-06) — Harden GitHub automation\n"
        "- [ ] **Owner:** Maintainers — Draft nightly workflow"
    )

    tasks = parse_tasks(section)

    assert len(tasks) == 2
    assert tasks[0].completed is True
    assert tasks[0].owner == "Assistant"
    assert tasks[0].due == date(2025, 10, 6)
    assert tasks[0].description == "Harden GitHub automation"
    assert tasks[1].completed is False
    assert tasks[1].owner == "Maintainers"
    assert tasks[1].due is None
    assert tasks[1].description == "Draft nightly workflow"


def test_summarize_tasks_counts_due_windows() -> None:
    now = date(2025, 10, 10)
    tasks = [
        TaskEntry(
            raw="",
            completed=False,
            owner="Maintainers",
            due=date(2025, 10, 5),
            description="Overdue item",
        ),
        TaskEntry(
            raw="",
            completed=False,
            owner="Assistant",
            due=date(2025, 10, 13),
            description="Due soon",
        ),
        TaskEntry(raw="", completed=False, owner=None, due=None, description="Backlog"),
        TaskEntry(
            raw="",
            completed=True,
            owner="Assistant",
            due=date(2025, 10, 9),
            description="Finished",
        ),
    ]

    summary = summarize_tasks(tasks, now=now, lookahead_days=4)

    assert summary["total_count"] == 4
    assert summary["open_count"] == 3
    assert summary["completed_count"] == 1
    assert summary["overdue_count"] == 1
    assert summary["due_soon_count"] == 1
    assert summary["overdue"][0].description == "Overdue item"
    assert summary["due_soon"][0].description == "Due soon"


def test_combine_status_escalates_on_overdue() -> None:
    coverage_payload = {
        "status": "at_risk",
        "emoji": "⚠️",
        "message": "Overall coverage 84%",
        "overall_coverage": 0.84,
        "target": 0.85,
    }
    summary = {
        "overdue_count": 1,
        "due_soon_count": 0,
        "open_count": 2,
        "completed_count": 0,
        "total_count": 2,
        "overdue": [
            TaskEntry(
                raw="",
                completed=False,
                owner="Maintainers",
                due=date(2025, 10, 1),
                description="Overdue",
            )
        ],
        "due_soon": [],
    }

    status = combine_status(coverage_payload, summary)

    assert status["status"] == "off_track"
    assert "overdue" in status["message"].lower()


def test_combine_status_defaults_when_coverage_missing() -> None:
    summary = {
        "overdue_count": 0,
        "due_soon_count": 0,
        "open_count": 0,
        "completed_count": 2,
        "total_count": 2,
        "overdue": [],
        "due_soon": [],
    }

    status = combine_status(None, summary)

    assert status["status"] == "on_track"
    assert "coverage data unavailable" in status["message"].lower()


def test_generate_report_reads_files(tmp_path: Path) -> None:
    next_steps_text = """# Next Steps

## Tasks

- [ ] **Owner:** Maintainers (Due: 2025-10-14) — Stand up dashboard automation
- [x] **Owner:** Assistant (Due: 2025-10-01) — Ship telemetry exporter

## Steps
- Item
"""
    next_steps_path = tmp_path / "Next Steps.md"
    next_steps_path.write_text(next_steps_text, encoding="utf-8")

    coverage_payload = {
        "status": "on_track",
        "emoji": "✅",
        "message": "Overall coverage 86% (target 85%)",
        "overall_coverage": 0.86,
        "target": 0.85,
        "recorded_at": "2025-10-09T12:00:00+00:00",
    }
    coverage_path = tmp_path / "coverage_projects_payload.json"
    coverage_path.write_text(json.dumps(coverage_payload), encoding="utf-8")

    report = generate_report(
        next_steps_paths=[next_steps_path],
        coverage_payload_path=coverage_path,
        now=datetime(2025, 10, 10, 12, 0, tzinfo=timezone.utc),
    )

    assert report["status"] == "at_risk"  # open task due soon
    assert report["coverage"]["status"] == "on_track"
    assert report["tasks"]["open_count"] == 1
    assert report["tasks"]["due_soon_count"] == 1
    assert report["tasks"]["entries"][0].owner == "Maintainers"


def test_render_comment_includes_sections() -> None:
    report = {
        "status": "off_track",
        "emoji": "❌",
        "coverage": {"message": "Coverage 80%"},
        "tasks": {
            "open_count": 2,
            "overdue_count": 1,
            "due_soon_count": 1,
            "overdue": [
                TaskEntry(
                    raw="",
                    completed=False,
                    owner="Maintainers",
                    due=date(2025, 10, 1),
                    description="Overdue task",
                )
            ],
            "due_soon": [
                TaskEntry(
                    raw="",
                    completed=False,
                    owner="Assistant",
                    due=date(2025, 10, 12),
                    description="Due soon task",
                )
            ],
        },
        "message": "Coverage 80% | 1 overdue task",
    }

    comment = render_comment(report)

    assert "Coverage 80%" in comment
    assert "Overdue task" in comment
    assert "Due soon task" in comment
    assert comment.startswith("❌")
