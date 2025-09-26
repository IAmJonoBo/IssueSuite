from __future__ import annotations

from typing import Any

from issuesuite.diffing import MAX_BODY_DIFF_LINES, compute_diff, needs_update
from issuesuite.models import IssueSpec


def _spec(**overrides: Any) -> IssueSpec:
    base: dict[str, Any] = {
        "external_id": "abc",
        "title": "Title",
        "labels": ["one", "two"],
        "milestone": "M1",
        "body": "<!-- issuesuite:slug=abc -->\n\nBody line\n",
        "status": "open",
        "project": None,
        "hash": "deadbeefcafebabe",
    }
    for k, v in overrides.items():
        base[k] = v
    # Strongly assert types for critical fields
    return IssueSpec(
        external_id=str(base["external_id"]),
        title=str(base["title"]),
        labels=list(base["labels"]),
        milestone=base["milestone"],
        body=str(base["body"]),
        status=base.get("status"),
        project=base.get("project"),
        hash=base.get("hash"),
    )


def test_needs_update_labels_changed() -> None:
    spec = _spec(labels=["one", "three"])
    issue: dict[str, Any] = {
        "labels": [{"name": "one"}, {"name": "two"}],
        "body": spec.body,
        "milestone": {"title": "M1"},
    }
    assert needs_update(spec, issue, prev_hash=None)


def test_needs_update_milestone_changed() -> None:
    spec = _spec(milestone="M2")
    issue: dict[str, Any] = {
        "labels": [{"name": lbl} for lbl in spec.labels],
        "body": spec.body,
        "milestone": {"title": "M1"},
    }
    assert needs_update(spec, issue, prev_hash=None)


def test_needs_update_body_changed() -> None:
    spec = _spec(body="<!-- issuesuite:slug=abc -->\n\nNew body\n")
    issue: dict[str, Any] = {
        "labels": [{"name": lbl} for lbl in spec.labels],
        "body": "<!-- issuesuite:slug=abc -->\n\nBody line\n",
        "milestone": {"title": "M1"},
    }
    assert needs_update(spec, issue, prev_hash=None)


def test_compute_diff_labels_and_body() -> None:
    spec = _spec(labels=["one", "three"], body="<!-- issuesuite:slug=abc -->\n\nNew body\n")
    issue: dict[str, Any] = {
        "labels": [{"name": "one"}, {"name": "two"}],
        "body": "<!-- issuesuite:slug=abc -->\n\nOld body\n",
        "milestone": {"title": "M1"},
    }
    diff: dict[str, Any] = compute_diff(spec, issue)
    assert diff["labels_added"] == ["three"]
    assert diff["labels_removed"] == ["two"]
    assert diff["body_changed"] is True
    assert any("Old body" in line or "New body" in line for line in diff["body_diff"])


def test_compute_diff_truncates_large_body_diff() -> None:
    original_lines = [f"Line {i}" for i in range(200)]
    new_lines = [f"Line {i}" for i in range(200)]
    new_lines[150] = "Changed line"
    spec = _spec(body="<!-- issuesuite:slug=abc -->\n" + "\n".join(new_lines) + "\n")
    issue: dict[str, Any] = {
        "labels": [{"name": lbl} for lbl in spec.labels],
        "body": "<!-- issuesuite:slug=abc -->\n" + "\n".join(original_lines) + "\n",
        "milestone": {"title": "M1"},
    }
    diff: dict[str, Any] = compute_diff(spec, issue)
    assert diff["body_changed"] is True
    assert len(diff["body_diff"]) <= MAX_BODY_DIFF_LINES + 1  # +1 for truncation marker
