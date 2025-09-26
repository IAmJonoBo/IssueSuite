"""Reconcile (drift detection) logic.

This module compares local parsed specs against the live issues fetched
from GitHub (as provided by the caller) and classifies drift into three
categories:

* ``spec_only``  – slug present locally but no matching live issue
* ``live_only``  – live issue (matching heuristic) not represented in specs
* ``diff``       – live + spec pair exist but fields differ (labels, milestone,
                                     or body content)

The matching heuristic prefers exact title match; if that fails we attempt
to match by embedded slug marker within the live issue body (marker format
``<!-- issuesuite:slug=<slug> -->``). This mirrors sync logic expectations
without depending on private core internals.

Output structure (stable for JSON tooling):

```
{
    "summary": {"spec_count": int, "live_count": int, "drift_count": int},
    "drift": [
            {"kind": "spec_only", "slug": str, "title": str},
            {"kind": "live_only", "number": int|None, "title": str, "slug": str|None},
            {"kind": "diff", "slug": str, "number": int|None, "title": str,
                 "changes": {... subset of diffing.compute_diff ...}}
    ],
    "in_sync": bool
}
```

The list is intentionally flat and small; consumers can group downstream.
Body diffs are truncated in ``diffing.compute_diff`` so we reuse that safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .diffing import compute_diff
from .models import IssueSpec

_MARKER_PREFIX = '<!-- issuesuite:slug='


@dataclass
class DriftRecord:  # retained for potential future richer typing
    kind: str  # spec_only | live_only | diff
    details: dict[str, Any]


def _index_specs(specs: list[IssueSpec]) -> dict[str, IssueSpec]:
    return {s.external_id: s for s in specs}


def _extract_slug_from_body(body: str | None) -> str | None:
    if not body:
        return None
    # Cheap substring then tight slice to avoid regex cost for large bodies
    idx = body.find(_MARKER_PREFIX)
    if idx == -1:
        return None
    tail = body[idx + len(_MARKER_PREFIX):]
    end = tail.find('-->')
    if end == -1:
        return None
    slug = tail[:end].strip()
    return slug or None


def _match_live_issue(issue: dict[str, Any], specs_by_slug: dict[str, IssueSpec]) -> IssueSpec | None:
    title = (issue.get('title') or '').strip()
    # Exact title match first (fast path)
    for spec in specs_by_slug.values():
        if spec.title == title:
            return spec
    # Fallback: slug marker in body
    slug = _extract_slug_from_body(issue.get('body'))
    if slug and slug in specs_by_slug:
        return specs_by_slug[slug]
    return None


def _build_live_drift(live_list: list[dict[str, Any]], specs_by_slug: dict[str, IssueSpec]) -> tuple[list[dict[str, Any]], set[str]]:
    drift: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for issue in live_list:
        spec = _match_live_issue(issue, specs_by_slug)
        if not spec:
            drift.append({
                'kind': 'live_only',
                'number': issue.get('number') if isinstance(issue.get('number'), int) else None,
                'title': issue.get('title'),
                'slug': _extract_slug_from_body(issue.get('body')),
            })
            continue
        seen_slugs.add(spec.external_id)
        changes = compute_diff(spec, issue)
        if changes:
            drift.append({
                'kind': 'diff',
                'slug': spec.external_id,
                'number': issue.get('number') if isinstance(issue.get('number'), int) else None,
                'title': spec.title,
                'changes': changes,
            })
    return drift, seen_slugs


def _append_spec_only(drift: list[dict[str, Any]], specs_by_slug: dict[str, IssueSpec], seen_slugs: set[str]) -> None:
    for slug, spec in specs_by_slug.items():
        if slug not in seen_slugs:
            drift.append({'kind': 'spec_only', 'slug': slug, 'title': spec.title})


def reconcile(*, specs: list[IssueSpec] | None, live_issues: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Compute drift between local specs and live issues.

    Parameters mirror CLI-layer responsibilities; fetching/parsing happens elsewhere.
    Returns structured drift report (see module docstring).
    """
    specs_list: list[IssueSpec] = list(specs or [])
    live_list: list[dict[str, Any]] = list(live_issues or [])
    specs_by_slug = _index_specs(specs_list)
    drift, seen_slugs = _build_live_drift(live_list, specs_by_slug)
    _append_spec_only(drift, specs_by_slug, seen_slugs)

    report = {
        'summary': {
            'spec_count': len(specs_list),
            'live_count': len(live_list),
            'drift_count': len(drift),
        },
        'drift': drift,
        'in_sync': len(drift) == 0,
    }
    return report


def format_report(report: dict[str, Any]) -> list[str]:  # return list of human lines
    summary = report.get('summary', {})
    lines: list[str] = []
    if report.get('in_sync'):
        lines.append(
            f"[reconcile] No drift detected (specs={summary.get('spec_count', 0)}, "
            f"live={summary.get('live_count', 0)})"
        )
        return lines
    lines.append(
        f"[reconcile] Drift items: {summary.get('drift_count')} (specs={summary.get('spec_count')}, "
        f"live={summary.get('live_count')})"
    )
    for entry in report.get('drift', []):
        kind = entry.get('kind')
        if kind == 'spec_only':
            lines.append(f"  spec_only: {entry.get('slug')} :: {entry.get('title')}")
        elif kind == 'live_only':
            lines.append(f"  live_only: #{entry.get('number')} :: {entry.get('title')} (slug={entry.get('slug')})")
        elif kind == 'diff':
            changes = entry.get('changes', {})
            change_keys = ','.join(sorted(k for k in changes.keys() if k.endswith('_added') or k.endswith('_removed') or k.endswith('_changed') or k in {'milestone_from','milestone_to'}))
            lines.append(f"  diff: {entry.get('slug')} fields_changed=[{change_keys}]")
    return lines

__all__ = ['reconcile', 'format_report', 'DriftRecord']
