from __future__ import annotations

from issuesuite.models import IssueSpec  # isort:skip
from issuesuite.reconcile import reconcile  # isort:skip

def make_spec(slug: str, title: str, labels: list[str] | None = None, milestone: str | None = None, body: str = 'Body') -> IssueSpec:  # minimal helper
    return IssueSpec(
        external_id=slug,
        title=title,
        labels=labels or [],
        milestone=milestone,
        body=body,
        status=None,
        project=None,
        hash='h',
    )


def test_reconcile_detects_all_categories() -> None:
    specs = [
        make_spec('slug-a', 'Title A', ['x']),
        make_spec('slug-b', 'Title B', ['y']),
        make_spec('slug-c', 'Title C', ['z']),
    ]
    # live issues: one matching but with label change, one extra, one missing
    live = [
        {
            'number': 101,
            'title': 'Title A',
            'labels': [{'name': 'x'}, {'name': 'added'}],
            'milestone': None,
            'body': 'Body <!-- issuesuite:slug=slug-a -->',
        },
        {
            'number': 102,
            'title': 'Orphan Live',
            'labels': [{'name': 'misc'}],
            'milestone': None,
            'body': 'Random body',
        },
    ]

    report = reconcile(specs=specs, live_issues=live)
    assert report['in_sync'] is False
    kinds = [d['kind'] for d in report['drift']]
    assert 'spec_only' in kinds  # slug-b or slug-c (one missing entirely, one will diff or be spec_only)
    assert 'live_only' in kinds
    assert 'diff' in kinds

    # basic structural expectations
    diff_entries = [d for d in report['drift'] if d['kind'] == 'diff']
    assert diff_entries and 'changes' in diff_entries[0]
