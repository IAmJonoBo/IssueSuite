from __future__ import annotations

import difflib
from typing import Any, TypedDict

from .models import IssueSpec


class _LabelDict(TypedDict, total=False):
    name: str


class _MilestoneDict(TypedDict, total=False):
    title: str


class _IssueDict(TypedDict, total=False):
    labels: list[_LabelDict]
    milestone: _MilestoneDict
    body: str


MAX_BODY_DIFF_LINES = 120


def extract_label_names(issue: dict[str, Any] | _IssueDict) -> set[str]:
    names: set[str] = set()
    labels_any = issue.get("labels")
    if isinstance(labels_any, list):
        for entry in labels_any:
            if isinstance(entry, dict):  # runtime defensive
                name_val = entry.get("name")
                if isinstance(name_val, str):
                    names.add(name_val)
    return names


def milestone_title(issue: dict[str, Any] | _IssueDict) -> str:
    ms_any = issue.get("milestone")
    if isinstance(ms_any, dict):
        title_val = ms_any.get("title")
        if isinstance(title_val, str):
            return title_val
    return ""


def needs_update(spec: IssueSpec, issue: dict[str, Any], prev_hash: str | None) -> bool:
    if prev_hash and prev_hash == spec.hash:
        return False
    existing_labels = extract_label_names(issue)
    if set(spec.labels) != existing_labels:
        return True
    desired_ms = spec.milestone or ""
    existing_ms = milestone_title(issue)
    if desired_ms != existing_ms:
        return True
    body = (issue.get("body") or "").strip()
    return body != spec.body.strip()


def compute_diff(spec: IssueSpec, issue: dict[str, Any]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    existing_labels = extract_label_names(issue)
    if set(spec.labels) != existing_labels:
        d["labels_added"] = sorted(set(spec.labels) - existing_labels)
        d["labels_removed"] = sorted(existing_labels - set(spec.labels))
    desired_ms = spec.milestone or ""
    existing_ms = milestone_title(issue)
    if desired_ms != existing_ms:
        d["milestone_from"] = existing_ms
        d["milestone_to"] = desired_ms
    old_body = (issue.get("body") or "").strip().splitlines()
    new_body = spec.body.strip().splitlines()
    if old_body != new_body:
        diff_lines = list(difflib.unified_diff(old_body, new_body, lineterm="", n=3))
        if len(diff_lines) > MAX_BODY_DIFF_LINES:
            diff_lines = diff_lines[:MAX_BODY_DIFF_LINES] + ["... (truncated)"]
        d["body_changed"] = True
        d["body_diff"] = diff_lines
    return d


__all__ = [
    "needs_update",
    "compute_diff",
    "extract_label_names",
    "milestone_title",
    "MAX_BODY_DIFF_LINES",
]
