from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any, cast

from .config import SuiteConfig
from .parser import parse_issues, render_yaml_block_from_fields
from .schemas import get_schemas

Draft7Validator: Any | None
_AGENT_UPDATE_VALIDATOR: Any | None = None
_DOC_ALLOWED_KEYS = {"path", "append", "replace"}
try:  # pragma: no cover - optional dependency import guard
    from jsonschema import Draft7Validator as _Draft7Validator
except Exception:  # pragma: no cover
    Draft7Validator = None
else:
    Draft7Validator = _Draft7Validator


def _now_date() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


_SLUG_RE = re.compile(r"^##\s*\[slug:\s*([a-z0-9][a-z0-9-_]*)\s*\]$", re.IGNORECASE)


def _ensure_body_marker(body: str, slug: str) -> str:
    marker = f"<!-- issuesuite:slug={slug} -->"
    if marker in body:
        return body
    if not body.endswith("\n"):
        body += "\n"
    return marker + "\n\n" + body


def _render_yaml_block(data: dict[str, Any]) -> list[str]:
    return render_yaml_block_from_fields(
        title=cast(str, data.get("title") or ""),
        labels=cast(list[str] | None, data.get("labels")),
        milestone=cast(str | None, data.get("milestone")),
        status=cast(str | None, data.get("status")),
        body=cast(str, data.get("body") or ""),
    )


def _append_summary_to_body(body: str, slug: str, summary: str) -> str:
    if not summary.strip():
        return body
    stamp = _now_date()
    addition = f"\n\n### Completion summary ({stamp})\n{summary.strip()}\n"
    body2 = body or ""
    if not body2.endswith("\n"):
        body2 += "\n"
    return _ensure_body_marker(body2 + addition, slug)


def _normalize_updates(data: Any) -> list[dict[str, Any]]:
    # Accept list, dict with "updates", or mapping slug->update
    if isinstance(data, list):
        return [cast(dict[str, Any], x) for x in data]
    if isinstance(data, dict):
        if "updates" in data and isinstance(data["updates"], list):
            return [cast(dict[str, Any], x) for x in data["updates"]]
        # mapping form
        items: list[dict[str, Any]] = []
        for k, v in data.items():
            if isinstance(v, dict):
                item = dict(v)
                item.setdefault("slug", k)
                items.append(item)
        return items
    # raw string: try JSON
    if isinstance(data, str):
        try:
            return _normalize_updates(json.loads(data))
        except Exception:
            return []
    return []


def _format_error_path(parts: list[Any]) -> str:
    return "/".join(str(p) for p in parts)


def _collect_manual_validation_errors(updates: list[Any]) -> list[str]:
    errors: list[str] = []
    for idx, upd in enumerate(updates):
        if not isinstance(upd, dict):
            errors.append(f"{idx}: update must be an object")
            continue
        slug = upd.get('slug')
        external_id = upd.get('external_id')
        if not isinstance(slug, str) or not slug.strip():
            if not isinstance(external_id, str) or not external_id.strip():
                errors.append(f"{idx}: missing slug or external_id")
        docs = upd.get('docs')
        if docs is None:
            continue
        if not isinstance(docs, list):
            errors.append(f"{idx}/docs: must be an array of objects")
            continue
        for doc_idx, doc in enumerate(docs):
            if not isinstance(doc, dict):
                errors.append(f"{idx}/docs/{doc_idx}: must be an object")
                continue
            path = doc.get('path')
            if not isinstance(path, str) or not path.strip():
                errors.append(f"{idx}/docs/{doc_idx}/path: must be a non-empty string")
            for key in ('append', 'replace'):
                if key in doc and doc[key] is not None and not isinstance(doc[key], str):
                    errors.append(f"{idx}/docs/{doc_idx}/{key}: must be a string")
            extra = sorted(k for k in doc.keys() if k not in _DOC_ALLOWED_KEYS)
            if extra:
                errors.append(
                    f"{idx}/docs/{doc_idx}: unsupported keys {', '.join(extra)}"
                )
    return errors


def _validate_updates(updates: list[dict[str, Any]]) -> None:
    all_errors: list[str] = []
    all_errors.extend(_collect_manual_validation_errors(cast(list[Any], updates)))

    if _AGENT_UPDATE_VALIDATOR is not None:
        schema_errors = sorted(
            _AGENT_UPDATE_VALIDATOR.iter_errors(updates),
            key=lambda err: list(err.path),
        )
        for err in schema_errors:
            location = _format_error_path(list(err.path))
            if location:
                message = f"{location}: {err.message}"
            else:
                message = err.message
            all_errors.append(message)

    if all_errors:
        deduped: list[str] = []
        seen: set[str] = set()
        for msg in all_errors:
            if msg not in seen:
                deduped.append(msg)
                seen.add(msg)
        raise ValueError("Agent update validation failed: " + "; ".join(deduped))


def _build_index(lines: list[str]) -> dict[str, tuple[int, int, list[str]]]:
    index: dict[str, tuple[int, int, list[str]]] = {}
    i = 0
    while i < len(lines):
        m = _SLUG_RE.match(lines[i])
        if not m:
            i += 1
            continue
        slug = m.group(1)
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or not lines[j].strip().startswith("```yaml"):
            i += 1
            continue
        j += 1
        yaml_block: list[str] = []
        while j < len(lines) and not lines[j].strip().startswith("```"):
            yaml_block.append(lines[j])
            j += 1
        if j < len(lines):
            j += 1
        index[slug] = (i, j, yaml_block)
        i = j
    return index


def _apply_doc_update(entry: dict[str, Any], slug: str, base_dir: Path) -> str | None:
    path = cast(str | None, entry.get("path"))
    if not path:
        return None
    abs_path = Path(path)
    if not abs_path.is_absolute():
        abs_path = base_dir / abs_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    if "replace" in entry and isinstance(entry["replace"], str):
        abs_path.write_text(entry["replace"], encoding="utf-8")
        return str(abs_path)
    if "append" in entry and isinstance(entry["append"], str):
        header = f"\n\n<!-- update-from: {slug} ({_now_date()}) -->\n"
        with abs_path.open("a", encoding="utf-8") as fh:
            fh.write(header)
            fh.write(entry["append"])
            if not entry["append"].endswith("\n"):
                fh.write("\n")
        return str(abs_path)
    # default: touch with a marker to show provenance
    with abs_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n\n<!-- update-from: {slug} ({_now_date()}) -->\n")
    return str(abs_path)


def _update_issue_yaml(upd: dict[str, Any]) -> list[str]:
    # This function is now a thin adapter; actual data comes from IssueSpec via parser.
    # The caller will provide the updated fields; we only render.
    return _render_yaml_block(upd)


def apply_agent_updates(
    cfg: SuiteConfig, updates: dict[str, Any] | list[dict[str, Any]]
) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
    """Apply agent-provided updates to ISSUES.md and optional docs.

    Input schema (flexible): list of objects with keys:
      - slug | external_id | title (at least one of slug/external_id)
      - completed: bool (true -> status closed)
      - status: 'open' | 'closed'
      - comment | summary: text to append to issue body under a dated heading
      - docs: [{ path, append?, replace? }]
    """
    issues_path: Path = cfg.source_file
    text = issues_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    index = _build_index(lines)

    # Parse canonical specs once using central parser
    specs = parse_issues(lines)
    by_slug: dict[str, Any] = {s.external_id: s for s in specs}

    updates_list = _normalize_updates(updates)
    _validate_updates(updates_list)
    changed_files, not_found = _apply_updates_to_issues_and_docs(
        issues_path, lines, index, updates_list, by_slug
    )

    # Persist ISSUES.md if changed
    if str(issues_path) in changed_files:
        text_out = "\n".join(lines)
        if not text_out.endswith("\n"):
            text_out += "\n"
        issues_path.write_text(text_out, encoding="utf-8")

    return {
        "changed_files": sorted(changed_files),
        "not_found": not_found,
        "updates_count": len(updates_list),
    }


def _apply_updates_to_issues_and_docs(  # noqa: C901, PLR0912, PLR0915
    issues_path: Path,
    lines: list[str],
    index: dict[str, tuple[int, int, list[str]]],
    updates_list: list[dict[str, Any]],
    by_slug: dict[str, Any],
) -> tuple[set[str], list[str]]:
    changed_files: set[str] = set()
    not_found: list[str] = []

    def _write_block(slug: str, start: int, end: int, yaml_block: list[str]) -> None:
        new_block = [f"## [slug: {slug}]", "", "```yaml"] + yaml_block + ["```", ""]
        lines[start:end] = new_block

    for upd in updates_list:
        slug = cast(str | None, upd.get("slug") or upd.get("external_id"))
        if not slug:
            continue
        entry = index.get(slug)
        if not entry:
            not_found.append(slug)
            continue
        start, end, _ylines = entry

        # Derive updated fields from parsed IssueSpec
        spec = by_slug.get(slug)
        if spec is None:
            not_found.append(slug)
            continue

        # Build new data dict for rendering
        data: dict[str, Any] = {
            "title": spec.title,
            "labels": list(spec.labels),
            "milestone": spec.milestone,
            "status": spec.status,
            "body": spec.body,
        }

        # Apply status/completion semantics
        completed = bool(upd.get("completed", False))
        status = cast(str | None, upd.get("status"))
        if completed and (not status or status.lower() not in {"open", "closed"}):
            status = "closed"
        if status:
            data["status"] = status

        # Append comment/summary
        comment = cast(str | None, upd.get("comment") or upd.get("summary"))
        if comment:
            body = cast(str, data.get("body") or "")
            body = _append_summary_to_body(body, slug, comment)
            data["body"] = body

        # Ensure marker present
        if "body" in data and isinstance(data["body"], str):
            data["body"] = _ensure_body_marker(data["body"], slug)

        new_yaml_lines = _update_issue_yaml(data)
        _write_block(slug, start, end, new_yaml_lines)
        changed_files.add(str(issues_path))

        docs = cast(list[dict[str, Any]] | None, upd.get("docs"))
        if docs:
            for d in docs:
                changed = _apply_doc_update(d, slug, issues_path.parent)
                if changed:
                    changed_files.add(changed)

    return changed_files, not_found


__all__ = [
    "apply_agent_updates",
]
if Draft7Validator is not None:
    try:
        _AGENT_UPDATE_VALIDATOR = Draft7Validator(get_schemas()["agent_updates"])
    except Exception:  # pragma: no cover - validation optional fallback
        _AGENT_UPDATE_VALIDATOR = None
