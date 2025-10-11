from typing import Any

from issuesuite.core import (
    _build_plan,
    _ensure_marker,
    _plan_changes,
    _plan_entry_for_spec,
    _plan_match_issue,
)
from issuesuite.models import IssueSpec


def _make_issue_spec(**overrides: Any) -> IssueSpec:
    base: dict[str, Any] = {
        "external_id": "frontier-apex",
        "title": "Frontier Apex launch",
        "labels": ["governance"],
        "milestone": None,
        "body": "Finalize blueprint",
        "status": "open",
    }
    base.update(overrides)
    return IssueSpec(**base)


def test_ensure_marker_idempotent() -> None:
    body = "## Heading"
    with_marker = _ensure_marker(body, "frontier-apex")

    assert with_marker.startswith("<!-- issuesuite:slug=frontier-apex -->")
    assert _ensure_marker(with_marker, "frontier-apex") == with_marker


def test_plan_entry_create_when_missing() -> None:
    spec = _make_issue_spec()

    entry = _plan_entry_for_spec(spec, [], {}, update=True, respect_status=True)

    assert entry["action"] == "create"
    assert entry["number"] is None


def test_plan_entry_close_when_status_closed() -> None:
    spec = _make_issue_spec(status="closed")
    existing = [{"title": "Frontier Apex launch", "state": "OPEN", "number": 7}]

    entry = _plan_entry_for_spec(spec, existing, {}, update=True, respect_status=True)

    assert entry["action"] == "close"
    assert entry["number"] == 7


def test_plan_entry_update_when_labels_change() -> None:
    spec = _make_issue_spec(labels=["governance", "ux"], body="Finalize blueprint v2")
    existing = [
        {
            "title": "Frontier Apex launch",
            "number": 3,
            "labels": [{"name": "governance"}],
            "body": "Finalize blueprint",
        }
    ]

    entry = _plan_entry_for_spec(spec, existing, {}, update=True, respect_status=True)

    assert entry["action"] == "update"
    assert entry["changes"]["labels_added"] == 1
    assert entry["changes"]["body_changed"] == 1


def test_plan_entry_skip_when_hash_matches() -> None:
    spec = _make_issue_spec(hash="abc123")
    existing = [
        {
            "title": "Frontier Apex launch",
            "number": 9,
            "labels": [{"name": "governance"}],
            "body": "Finalize blueprint",
        }
    ]

    entry = _plan_entry_for_spec(
        spec,
        existing,
        {"frontier-apex": "abc123"},
        update=True,
        respect_status=True,
    )

    assert entry["action"] == "skip"
    assert entry["number"] == 9


def test_plan_match_issue_fuzzy_slug() -> None:
    spec = _make_issue_spec()
    existing = [
        {
            "title": "Frontier Apex launch (frontier-apex)",
            "number": 11,
        }
    ]

    match = _plan_match_issue(spec, existing)

    assert match is not None
    assert match["number"] == 11


def test_build_plan_aggregates_entries() -> None:
    spec_open = _make_issue_spec()
    spec_closed = _make_issue_spec(external_id="frontier-done", title="Frontier done", status="closed")
    existing = [
        {"title": "Frontier done", "state": "OPEN", "number": 5, "labels": [], "body": ""},
    ]

    plan = _build_plan([spec_open, spec_closed], existing, {}, update=True, respect_status=True)

    actions = {entry["external_id"]: entry["action"] for entry in plan}
    assert actions["frontier-apex"] == "create"
    assert actions["frontier-done"] == "close"


def test_plan_changes_counts_differences() -> None:
    spec = _make_issue_spec(labels=["governance", "ux"], milestone="Launch", body="New body")
    issue = {
        "labels": [{"name": "governance"}],
        "milestone": {"title": "Old"},
        "body": "Old body",
    }

    changes = _plan_changes(spec, issue)

    assert changes["labels_added"] == 1
    assert changes["labels_removed"] == 0
    assert changes["body_changed"] == 1
    assert changes["milestone_changed"] == 1
