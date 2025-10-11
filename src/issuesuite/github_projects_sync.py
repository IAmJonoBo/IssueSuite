# ruff: noqa: PLR0912

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .projects_status import generate_report, render_comment, serialize_report

GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
HTTP_OK = 200
DEFAULT_STATUS_MAPPING = {
    "on_track": "On Track",
    "at_risk": "At Risk",
    "off_track": "Off Track",
}


class ProjectsSyncError(RuntimeError):
    """Raised when the GitHub Projects automation encounters a failure."""


@dataclass(frozen=True)
class ProjectsSyncConfig:
    """Runtime configuration for GitHub Projects synchronisation."""

    owner: str | None
    project_number: int | None
    owner_type: str
    item_title: str
    status_field: str
    status_mapping: Mapping[str, str]
    coverage_field: str | None = None
    summary_field: str | None = None
    comment_repo: str | None = None
    comment_issue: int | None = None
    token: str | None = None

    def requires_project_sync(self) -> bool:
        return bool(self.owner and self.project_number is not None)

    def requires_comment(self) -> bool:
        return bool(self.comment_repo and self.comment_issue is not None)


@dataclass(frozen=True)
class _ProjectField:
    id: str
    name: str
    data_type: str
    options: dict[str, str] | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> _ProjectField:
        options_payload = payload.get("options")
        options: dict[str, str] | None = None
        if isinstance(options_payload, Mapping):
            nodes = options_payload.get("nodes")
            if isinstance(nodes, list):
                options = {}
                for node in nodes:
                    if not isinstance(node, Mapping):
                        continue
                    option_id = node.get("id")
                    option_name = node.get("name")
                    if isinstance(option_id, str) and isinstance(option_name, str):
                        options[option_name.casefold()] = option_id
        return cls(
            id=str(payload.get("id")),
            name=str(payload.get("name")),
            data_type=str(payload.get("dataType", "")),
            options=options,
        )


@dataclass(frozen=True)
class _ProjectMetadata:
    project_id: str
    item_id: str | None
    fields: dict[str, _ProjectField]


def _parse_status_mapping(
    values: list[str] | None, *, defaults: Mapping[str, str] | None = None
) -> dict[str, str]:
    mapping: dict[str, str] = dict(defaults or DEFAULT_STATUS_MAPPING)
    if not values:
        return mapping
    for raw in values:
        if "=" not in raw:
            raise ProjectsSyncError(f"Invalid status mapping '{raw}'; expected format key=value")
        key, value = raw.split("=", 1)
        key = key.strip().casefold()
        value = value.strip()
        if not key or not value:
            raise ProjectsSyncError(f"Invalid status mapping '{raw}'; empty key or value")
        mapping[key] = value
    return mapping


def build_config(
    *,
    owner: str | None,
    project_number: int | None,
    owner_type: str | None,
    item_title: str | None,
    status_field: str | None,
    status_mapping: list[str] | None,
    coverage_field: str | None,
    summary_field: str | None,
    comment_repo: str | None,
    comment_issue: int | None,
    token: str | None,
) -> ProjectsSyncConfig:
    mapping = _parse_status_mapping(status_mapping)
    resolved_owner_type = (owner_type or "organization").lower()
    if resolved_owner_type not in {"organization", "user"}:
        raise ProjectsSyncError("owner_type must be either 'organization' or 'user'")
    return ProjectsSyncConfig(
        owner=owner,
        project_number=project_number,
        owner_type=resolved_owner_type,
        item_title=item_title or "IssueSuite Health",
        status_field=status_field or "Status",
        status_mapping=mapping,
        coverage_field=coverage_field,
        summary_field=summary_field,
        comment_repo=comment_repo,
        comment_issue=comment_issue,
        token=token,
    )


def build_sync_plan(
    *,
    next_steps_paths: list[Path] | None = None,
    coverage_payload_path: Path | None = None,
    lookahead_days: int | None = None,
) -> dict[str, Any]:
    report = generate_report(
        next_steps_paths=next_steps_paths,
        coverage_payload_path=coverage_payload_path,
        lookahead_days=lookahead_days,
    )
    comment = render_comment(report) + "\n"
    serialized = serialize_report(report)
    return {
        "report": serialized,
        "comment": comment,
        "status": report.get("status"),
        "coverage": report.get("coverage", {}),
    }


def sync_projects(
    *,
    config: ProjectsSyncConfig,
    next_steps_paths: list[Path] | None = None,
    coverage_payload_path: Path | None = None,
    lookahead_days: int | None = None,
    comment_output: Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    plan = build_sync_plan(
        next_steps_paths=next_steps_paths,
        coverage_payload_path=coverage_payload_path,
        lookahead_days=lookahead_days,
    )
    if comment_output:
        comment_output.write_text(plan["comment"], encoding="utf-8")

    project_result: dict[str, Any] = {
        "enabled": config.requires_project_sync(),
        "updated": False,
        "dry_run": not apply,
    }
    comment_result: dict[str, Any] = {
        "enabled": config.requires_comment(),
        "updated": False,
        "dry_run": not apply,
    }

    if apply:
        if config.requires_project_sync():
            if not config.token:
                raise ProjectsSyncError("GitHub token required to update Projects")
            project_result = _apply_project_update(config, plan)
        if config.requires_comment():
            if not config.token:
                raise ProjectsSyncError("GitHub token required to post status comment")
            comment_result = _post_status_comment(config, plan["comment"])
    else:
        if config.requires_project_sync():
            project_result = _project_plan_preview(config, plan)
        if config.requires_comment():
            comment_result = _comment_plan_preview(config, plan["comment"])

    return {
        "report": plan["report"],
        "comment": plan["comment"],
        "project": project_result,
        "comment_result": comment_result,
    }


def _project_plan_preview(config: ProjectsSyncConfig, plan: Mapping[str, Any]) -> dict[str, Any]:
    status = str(plan.get("status") or "").casefold()
    status_label = config.status_mapping.get(status)
    coverage = plan.get("coverage") or {}
    overall = coverage.get("overall_coverage")
    coverage_percent = overall * 100 if isinstance(overall, (int, float)) else None
    return {
        "enabled": True,
        "updated": False,
        "dry_run": True,
        "status": status,
        "status_label": status_label,
        "coverage_percent": coverage_percent,
        "summary": plan["report"].get("message"),
    }


def _comment_plan_preview(config: ProjectsSyncConfig, body: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "updated": False,
        "dry_run": True,
        "repo": config.comment_repo,
        "issue": config.comment_issue,
        "length": len(body),
    }


def _create_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "issuesuite-projects-sync",
        }
    )
    return session


def _apply_project_update(config: ProjectsSyncConfig, plan: Mapping[str, Any]) -> dict[str, Any]:
    session = _create_session(config.token or "")
    metadata = _fetch_project_metadata(session, config)

    item_id = metadata.item_id
    created_item = False
    if item_id is None:
        title = config.item_title
        if not title:
            raise ProjectsSyncError("Project item title required to create status entry")
        item_id = _create_project_item(
            session,
            project_id=metadata.project_id,
            title=title,
        )
        created_item = True

    status = str(plan.get("status") or "").casefold()
    status_label = config.status_mapping.get(status)
    if status_label is None:
        raise ProjectsSyncError(
            f"No status mapping configured for '{status}' (expected keys: {sorted(config.status_mapping)})"
        )
    coverage = plan.get("coverage") or {}
    overall = coverage.get("overall_coverage")
    coverage_percent = overall * 100 if isinstance(overall, (int, float)) else None
    summary = plan["report"].get("message")

    if config.status_field:
        _update_single_select_field(
            session,
            project_id=metadata.project_id,
            item_id=item_id,
            field=_resolve_field(metadata, config.status_field),
            label=status_label,
        )
    if coverage_percent is not None and config.coverage_field:
        _update_number_field(
            session,
            project_id=metadata.project_id,
            item_id=item_id,
            field=_resolve_field(metadata, config.coverage_field),
            value=coverage_percent,
        )
    if summary and config.summary_field:
        _update_text_field(
            session,
            project_id=metadata.project_id,
            item_id=item_id,
            field=_resolve_field(metadata, config.summary_field),
            value=summary,
        )

    return {
        "enabled": True,
        "updated": True,
        "dry_run": False,
        "project_id": metadata.project_id,
        "item_id": item_id,
        "status": status,
        "status_label": status_label,
        "coverage_percent": coverage_percent,
        "created_item": created_item,
    }


def _resolve_field(metadata: _ProjectMetadata, name: str) -> _ProjectField:
    key = name.casefold()
    for candidate in metadata.fields.values():
        if candidate.name.casefold() == key:
            return candidate
    raise ProjectsSyncError(
        f"Project field '{name}' not found; available: {sorted(metadata.fields)}"
    )


def _fetch_project_metadata(
    session: requests.Session, config: ProjectsSyncConfig
) -> _ProjectMetadata:  # noqa: PLR0912
    if not config.owner or config.project_number is None:
        raise ProjectsSyncError("Owner and project number are required for project synchronisation")
    root_field = "organization" if config.owner_type == "organization" else "user"
    query = f"""
    query($owner: String!, $number: Int!, $itemQuery: String) {{
      {root_field}(login: $owner) {{
        projectV2(number: $number) {{
          id
          title
          fields(first: 100) {{
            nodes {{
              id
              name
              dataType
              ... on ProjectV2SingleSelectField {{
                options {{
                  nodes {{
                    id
                    name
                  }}
                }}
              }}
            }}
          }}
          items(first: 50, query: $itemQuery) {{
            nodes {{
              id
              title
            }}
          }}
        }}
      }}
    }}
    """
    variables = {
        "owner": config.owner,
        "number": config.project_number,
        "itemQuery": config.item_title,
    }
    response = session.post(
        GITHUB_GRAPHQL_ENDPOINT,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    if response.status_code != HTTP_OK:
        raise ProjectsSyncError(
            f"GraphQL query failed with HTTP {response.status_code}: {response.text}"
        )
    payload = response.json()
    if "errors" in payload:
        raise ProjectsSyncError(f"GraphQL query returned errors: {payload['errors']}")
    data = payload.get("data", {})
    owner_payload = data.get(root_field) if isinstance(data, Mapping) else None
    if not owner_payload or not isinstance(owner_payload, Mapping):
        raise ProjectsSyncError(f"Project owner '{config.owner}' not found")
    project_payload = owner_payload.get("projectV2")
    if not project_payload or not isinstance(project_payload, Mapping):
        raise ProjectsSyncError(
            f"Project {config.owner}/{config.project_number} not accessible with provided token"
        )
    project_id = project_payload.get("id")
    if not isinstance(project_id, str):
        raise ProjectsSyncError("Project response missing id")

    fields_payload = project_payload.get("fields", {})
    nodes = fields_payload.get("nodes") if isinstance(fields_payload, Mapping) else None
    fields: dict[str, _ProjectField] = {}
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, Mapping):
                field = _ProjectField.from_payload(node)
                fields[field.name.casefold()] = field

    items_payload = project_payload.get("items", {})
    item_nodes = items_payload.get("nodes") if isinstance(items_payload, Mapping) else None
    item_id: str | None = None
    if isinstance(item_nodes, list):
        for node in item_nodes:
            if not isinstance(node, Mapping):
                continue
            title = node.get("title")
            candidate_id = node.get("id")
            if isinstance(title, str) and isinstance(candidate_id, str):
                if title.strip().casefold() == config.item_title.casefold():
                    item_id = candidate_id
                    break

    return _ProjectMetadata(project_id=project_id, item_id=item_id, fields=fields)


def _create_project_item(session: requests.Session, *, project_id: str, title: str) -> str:
    mutation = """
    mutation($projectId: ID!, $title: String!) {
      addProjectV2ItemByTitle(input: {projectId: $projectId, title: $title}) {
        item {
          id
        }
      }
    }
    """
    response = session.post(
        GITHUB_GRAPHQL_ENDPOINT,
        json={
            "query": mutation,
            "variables": {"projectId": project_id, "title": title},
        },
        timeout=30,
    )
    if response.status_code != HTTP_OK:
        raise ProjectsSyncError(
            f"Failed to create draft item (HTTP {response.status_code}): {response.text}"
        )
    payload = response.json()
    if "errors" in payload:
        raise ProjectsSyncError(f"Draft item creation failed: {payload['errors']}")
    data = payload.get("data", {})
    add_payload = data.get("addProjectV2ItemByTitle") if isinstance(data, Mapping) else None
    item_payload = add_payload.get("item") if isinstance(add_payload, Mapping) else None
    item_id = item_payload.get("id") if isinstance(item_payload, Mapping) else None
    if not isinstance(item_id, str):
        raise ProjectsSyncError("Draft item creation returned invalid payload")
    return item_id


def _update_single_select_field(
    session: requests.Session,
    *,
    project_id: str,
    item_id: str,
    field: _ProjectField,
    label: str,
) -> None:
    if not field.options:
        raise ProjectsSyncError(f"Field '{field.name}' does not expose selectable options")
    option_id = field.options.get(label.casefold())
    if option_id is None:
        raise ProjectsSyncError(f"Option '{label}' not found for field '{field.name}'")
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: {singleSelectOptionId: $optionId}}
      ) {
        projectV2Item { id }
      }
    }
    """
    response = session.post(
        GITHUB_GRAPHQL_ENDPOINT,
        json={
            "query": mutation,
            "variables": {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field.id,
                "optionId": option_id,
            },
        },
        timeout=30,
    )
    _validate_mutation_response(response, f"update field '{field.name}'")


def _update_number_field(
    session: requests.Session,
    *,
    project_id: str,
    item_id: str,
    field: _ProjectField,
    value: float,
) -> None:
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: Float!) {
      updateProjectV2ItemFieldValue(
        input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: {number: $value}}
      ) {
        projectV2Item { id }
      }
    }
    """
    response = session.post(
        GITHUB_GRAPHQL_ENDPOINT,
        json={
            "query": mutation,
            "variables": {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field.id,
                "value": value,
            },
        },
        timeout=30,
    )
    _validate_mutation_response(response, f"update field '{field.name}'")


def _update_text_field(
    session: requests.Session,
    *,
    project_id: str,
    item_id: str,
    field: _ProjectField,
    value: str,
) -> None:
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: String!) {
      updateProjectV2ItemFieldValue(
        input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: {text: $value}}
      ) {
        projectV2Item { id }
      }
    }
    """
    response = session.post(
        GITHUB_GRAPHQL_ENDPOINT,
        json={
            "query": mutation,
            "variables": {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field.id,
                "value": value,
            },
        },
        timeout=30,
    )
    _validate_mutation_response(response, f"update field '{field.name}'")


def _validate_mutation_response(response: requests.Response, action: str) -> None:
    if response.status_code != HTTP_OK:
        raise ProjectsSyncError(
            f"Failed to {action} (HTTP {response.status_code}): {response.text}"
        )
    payload = response.json()
    if "errors" in payload:
        raise ProjectsSyncError(f"GitHub rejected request to {action}: {payload['errors']}")


def _post_status_comment(config: ProjectsSyncConfig, body: str) -> dict[str, Any]:
    if not config.comment_repo or config.comment_issue is None:
        raise ProjectsSyncError("Comment repository and issue must be configured")
    session = _create_session(config.token or "")
    url = (
        f"https://api.github.com/repos/{config.comment_repo}/issues/{config.comment_issue}/comments"
    )
    response = session.post(url, json={"body": body}, timeout=30)
    if response.status_code not in {200, 201}:
        raise ProjectsSyncError(
            f"Failed to post status comment (HTTP {response.status_code}): {response.text}"
        )
    payload = response.json()
    return {
        "enabled": True,
        "updated": True,
        "dry_run": False,
        "id": payload.get("id"),
        "repo": config.comment_repo,
        "issue": config.comment_issue,
    }


__all__ = [
    "ProjectsSyncError",
    "ProjectsSyncConfig",
    "build_config",
    "build_sync_plan",
    "sync_projects",
]
