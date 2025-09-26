from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any, TypedDict, cast

from .models import IssueSpec

try:  # optional import; caller should guard
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = cast(Any, None)

LABEL_CANON_MAP = {
    'p0-critical': 'P0-critical',
    'p1-important': 'P1-important',
    'p2-enhancement': 'P2-enhancement',
}


class ParseError(ValueError):
    pass


_slug_re = re.compile(r'^##\s*\[slug:\s*([a-z0-9][a-z0-9-_]*)\s*\]$', re.IGNORECASE)


def _normalize_body(body_any: Any) -> str:
    if isinstance(body_any, list):
        return '\n'.join(str(x) for x in body_any) + '\n'
    body_s = str(body_any)
    return body_s if body_s.endswith('\n') else body_s + '\n'


class _IssueYAML(TypedDict, total=False):
    title: str
    body: Any
    labels: list[str] | str
    milestone: str
    status: str
    project: dict[str, Any]


def _parse_single(slug: str, block: list[str]) -> IssueSpec:  # noqa: C901 - acceptable explicit mapping
    if _yaml is None:  # pragma: no cover - validated earlier
        raise RuntimeError('PyYAML is required for parsing')
    try:
        loaded_any = _yaml.safe_load('\n'.join(block)) or {}
    except Exception as exc:  # pragma: no cover
        raise ParseError(f'Invalid YAML for slug {slug}: {exc}') from exc
    if not isinstance(loaded_any, dict):
        raise ParseError(f'YAML for slug {slug} must be a mapping')
    data = cast(_IssueYAML, loaded_any)
    title_any = data.get('title')
    if not isinstance(title_any, str) or not title_any.strip():
        raise ParseError(f'Missing title in slug {slug}')
    title = title_any.strip()
    body = _normalize_body(data.get('body', ''))
    marker = f'<!-- issuesuite:slug={slug} -->'
    if marker not in body:
        body = marker + '\n\n' + body
    labels_any = data.get('labels')
    label_tokens: list[str] = []
    if isinstance(labels_any, str):
        label_tokens = [p.strip() for p in labels_any.split(',') if p.strip()]
    elif isinstance(labels_any, list):
        label_tokens = [str(p).strip() for p in labels_any if str(p).strip()]
    labels = [LABEL_CANON_MAP.get(lbl.lower(), lbl) for lbl in label_tokens]
    milestone_val = data.get('milestone') if 'milestone' in data else None
    milestone = milestone_val if isinstance(milestone_val, str) else None
    status_val = data.get('status') if 'status' in data else None
    status = status_val if isinstance(status_val, str) else None
    project_val = data.get('project') if 'project' in data else None
    project_block = project_val if isinstance(project_val, dict) else None
    h = hashlib.sha256()
    h.update(
        '\x1f'.join(
            [
                slug,
                title,
                ','.join(sorted(labels)),
                milestone or '',
                status or '',
                body.strip(),
            ]
        ).encode('utf-8')
    )
    return IssueSpec(
        external_id=slug,
        title=title,
        labels=labels,
        milestone=milestone,
        body=body,
        status=status,
        project=project_block,
        hash=h.hexdigest()[:16],
    )


def parse_issues(lines: Iterable[str]) -> list[IssueSpec]:  # noqa: C901
    if _yaml is None:  # pragma: no cover
        raise RuntimeError('PyYAML is required for parsing')
    lines_list: list[str] = list(lines)
    i = 0
    specs: list[IssueSpec] = []
    while i < len(lines_list):
        line = lines_list[i]
        m = _slug_re.match(line)
        if not m:
            if re.match(r'^##\s+\d{3}\s*\|', line):
                raise ParseError('Legacy numeric issue format detected. Use slug+YAML format.')
            i += 1
            continue
        slug = m.group(1)
        i += 1
        while i < len(lines_list) and not lines_list[i].strip():
            i += 1
        if i >= len(lines_list) or not lines_list[i].strip().startswith('```yaml'):
            raise ParseError(f'Missing ```yaml fenced block for slug {slug}')
        i += 1
        block: list[str] = []
        while i < len(lines_list) and not lines_list[i].strip().startswith('```'):
            block.append(lines_list[i])
            i += 1
        if i >= len(lines_list):
            raise ParseError(f'Unterminated YAML block for slug {slug}')
        i += 1
        specs.append(_parse_single(slug, block))
    if not specs:
        raise ParseError('No slug headings found in ISSUES.md')
    return specs


__all__ = ["parse_issues", "ParseError", "IssueSpec"]
