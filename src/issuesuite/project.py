"""GitHub Project (v2) integration for IssueSuite with basic caching & option mapping.

Features:
    * Config-driven enablement
    * Mock mode (ISSUES_SUITE_MOCK=1) for deterministic offline tests
    * Lightweight caching (project id + field metadata) in .issuesuite_cache
        (TTL configurable via ISSUESUITE_PROJECT_CACHE_TTL, default 3600s; disable with ISSUESUITE_PROJECT_CACHE_DISABLE=1)
    * Option name -> ID mapping for single-select fields

Real GraphQL interactions are stubbed for now to keep tests deterministic and
avoid network dependencies. The public surface is stable for future expansion.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - GitHub CLI interactions require subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .logging import get_logger


@dataclass
class ProjectConfig:
    enabled: bool
    number: int | None
    field_mappings: dict[str, str]


class ProjectAssigner(Protocol):  # pragma: no cover - interface only
    def assign(self, issue_number: int, spec: Any) -> None: ...


class NoopProjectAssigner:
    def assign(self, issue_number: int, spec: Any) -> None:  # pragma: no cover - trivial
        return


class GitHubProjectAssigner:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.logger = get_logger()
        self._mock = os.environ.get('ISSUES_SUITE_MOCK') == '1'
        self._project_id: str | None = None
        self._field_cache: dict[str, dict[str, Any]] = {}
        self._cache_dir = Path('.issuesuite_cache')
        self._cache_dir.mkdir(exist_ok=True)
        self._cache_ttl = int(os.environ.get('ISSUESUITE_PROJECT_CACHE_TTL', '3600'))
        self._no_persist = os.environ.get('ISSUESUITE_PROJECT_CACHE_DISABLE') == '1'
        self._gh_cli_path: Path | None = None if self._mock else self._resolve_gh_cli()

    # ---------------- internal helpers ----------------
    def _cache_path(self) -> Path:
        return self._cache_dir / f"project_{self.config.number}_cache.json"

    def _is_cache_stale(self, payload: dict[str, Any]) -> bool:
        ts = payload.get('ts')
        if not isinstance(ts, int | float):
            return True
        return (time.time() - ts) > self._cache_ttl

    def _load_cache(self) -> dict[str, Any] | None:
        if self._no_persist:
            return None
        p = self._cache_path()
        if not p.exists():
            return None
        try:
            raw = json.loads(p.read_text())
            if isinstance(raw, dict):
                return raw
        except Exception:  # pragma: no cover - best effort
            return None
        return None

    def _save_cache(self) -> None:
        if self._no_persist:
            return
        try:
            payload = {
                'project_id': self._project_id,
                'fields': self._field_cache,
                'ts': time.time(),
            }
            self._cache_path().write_text(json.dumps(payload, indent=2))
        except Exception as exc:  # pragma: no cover - best effort
            self.logger.debug('Failed to persist project cache', error=str(exc))

    def _get_project_id(self) -> str | None:
        if self._project_id:
            return self._project_id
        cached = self._load_cache()
        if cached and cached.get('project_id') and not self._is_cache_stale(cached):
            self._project_id = str(cached['project_id'])
            if cached.get('fields') and not self._field_cache:
                # hydrate field cache from persisted payload
                self._field_cache = cached['fields']
            return self._project_id
        if self._mock:
            self._project_id = f"mock_project_{self.config.number}"
            self._save_cache()
            return self._project_id
        try:  # pragma: no cover - placeholder
            self.logger.debug("Fetching project ID", project_number=self.config.number)
            self._project_id = f"project_v2_{self.config.number}"
            self._save_cache()
            return self._project_id
        except Exception as e:  # pragma: no cover - defensive
            self.logger.log_error(
                f"Failed to get project ID for project {self.config.number}", error=str(e)
            )
            return None

    def _get_project_fields(self) -> dict[str, dict[str, Any]]:
        if self._field_cache:
            return self._field_cache
        cached = self._load_cache()
        if cached and cached.get('fields') and not self._is_cache_stale(cached):
            # hydrate from cache
            self._field_cache = cached['fields']
            return self._field_cache
        if self._mock:
            self._field_cache = {
                'Status': {
                    'id': 'field_status',
                    'type': 'single_select',
                    'options': {
                        'Todo': 'opt_status_todo',
                        'In Progress': 'opt_status_in_progress',
                        'Done': 'opt_status_done',
                    },
                },
                'Priority': {
                    'id': 'field_priority',
                    'type': 'single_select',
                    'options': {
                        'P0': 'opt_priority_p0',
                        'P1': 'opt_priority_p1',
                        'P2': 'opt_priority_p2',
                    },
                },
                'Assignee': {'id': 'field_assignee', 'type': 'assignees'},
            }
            self._save_cache()
            return self._field_cache
        try:  # pragma: no cover - placeholder
            if not self._get_project_id():
                return {}
            self.logger.debug("Fetching project fields", project_id=self._project_id)
            # Simulated subset; real call would populate dynamically
            self._field_cache = {
                'Status': {
                    'id': 'field_status',
                    'type': 'single_select',
                    'options': {
                        'Todo': 'opt_status_todo',
                        'In Progress': 'opt_status_in_progress',
                        'Done': 'opt_status_done',
                    },
                },
                'Priority': {
                    'id': 'field_priority',
                    'type': 'single_select',
                    'options': {
                        'P0': 'opt_priority_p0',
                        'P1': 'opt_priority_p1',
                        'P2': 'opt_priority_p2',
                    },
                },
            }
            self._save_cache()
            return self._field_cache
        except Exception as e:  # pragma: no cover - defensive
            self.logger.log_error("Failed to get project fields", error=str(e))
            return {}

    def _add_issue_to_project(self, issue_number: int) -> str | None:
        project_id = self._get_project_id()
        if not project_id:
            return None
        if self._mock:
            self.logger.info(f"MOCK: Add issue #{issue_number} to project {project_id}")
            return f"mock_item_{issue_number}"
        try:  # pragma: no cover - placeholder
            self.logger.debug(
                "Adding issue to project", issue_number=issue_number, project_id=project_id
            )
            item_id = f"project_item_{issue_number}"
            self.logger.info(f"Added issue #{issue_number} to project", item_id=item_id)
            return item_id
        except Exception as e:  # pragma: no cover - defensive
            self.logger.log_error(f"Failed to add issue #{issue_number} to project", error=str(e))
            return None

    def _get_issue_id(self, issue_number: int) -> str | None:
        """Return the GraphQL node id for an issue number.

        In mock mode we synthesize a deterministic value. Real mode shells out to
        'gh api' until a native abstraction is introduced. The method is kept
        for backwards compatibility with existing tests.
        """
        if self._mock:
            return f"mock_issue_{issue_number}"
        gh_path = self._gh_cli_path or self._resolve_gh_cli()
        if gh_path is None:
            gh_cmd = 'gh'
            self.logger.debug('GitHub CLI not resolved; attempting default "gh" lookup')
        else:
            gh_cmd = str(gh_path)
        try:  # pragma: no cover - placeholder shell call
            result = subprocess.run(  # nosec B603 B607 - GitHub CLI invocation with controlled arguments
                [
                    gh_cmd,
                    'api',
                    f'repos/:owner/:repo/issues/{issue_number}',
                    '--jq',
                    '.node_id',
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            issue_id = result.stdout.strip()
            if issue_id:
                self.logger.debug("Got issue ID", issue_number=issue_number, issue_id=issue_id)
            return issue_id or None
        except Exception as e:  # pragma: no cover - defensive
            self.logger.log_error(f"Failed to get issue ID for #{issue_number}", error=str(e))
            return None

    def _resolve_gh_cli(self) -> Path | None:
        if self._mock:
            return None
        gh_path = shutil.which('gh')
        if gh_path:
            self._gh_cli_path = Path(gh_path)
            return self._gh_cli_path
        self.logger.debug('GitHub CLI executable not found; project assigner limited to mock mode')
        self._gh_cli_path = None
        return None

    def _update_project_field(
        self, item_id: str, field_name: str, field_value: str | list[str]
    ) -> bool:
        fields = self._get_project_fields()
        info = fields.get(field_name)
        if not info:
            self.logger.warning(f"Field '{field_name}' not found in project")
            return False
        value_repr: str | list[str] = field_value
        if isinstance(field_value, str) and info.get('type') == 'single_select':
            options: dict[str, str] = info.get('options', {})
            if options:
                match_id = next(
                    (oid for name, oid in options.items() if name.lower() == field_value.lower()),
                    None,
                )
                if not match_id:
                    self.logger.warning(
                        f"Value '{field_value}' not found among options for field '{field_name}'",
                        field=field_name,
                        value=field_value,
                    )
                    return False
                value_repr = match_id
        if self._mock:
            self.logger.info(
                f"MOCK: Update field '{field_name}' = '{value_repr}' for item {item_id}"
            )
            return True
        try:  # pragma: no cover - placeholder
            if not self._get_project_id():
                return False
            self.logger.debug(
                "Updating project field",
                item_id=item_id,
                field_name=field_name,
                field_value=value_repr,
            )
            self.logger.info(f"Updated project field '{field_name}' for item {item_id}")
            return True
        except Exception as e:  # pragma: no cover
            self.logger.log_error(
                f"Failed to update field '{field_name}' for item {item_id}", error=str(e)
            )
            return False

    # ---------------- public API ----------------
    def _apply_field_mappings(self, item_id: str, spec: Any) -> None:
        for spec_field, project_field in self.config.field_mappings.items():
            if not hasattr(spec, spec_field):
                continue
            value = getattr(spec, spec_field)
            if not value:
                continue
            if isinstance(value, list):
                for v in value:
                    if self._update_project_field(item_id, project_field, v):
                        break
            else:
                self._update_project_field(item_id, project_field, value)

    def assign(self, issue_number: int, spec: Any) -> None:
        if not self.config.enabled or not self.config.number:
            return
        self.logger.log_operation(
            "project_assign_start", issue_number=issue_number, project_number=self.config.number
        )
        try:
            item_id = self._add_issue_to_project(issue_number)
            if not item_id:
                self.logger.log_error(f"Failed to add issue #{issue_number} to project")
                return
            self._apply_field_mappings(item_id, spec)
            self.logger.log_operation(
                "project_assign_complete",
                issue_number=issue_number,
                project_number=self.config.number,
                item_id=item_id,
            )
        except Exception as e:  # pragma: no cover - defensive
            self.logger.log_error(
                f"Failed to assign issue #{issue_number} to project", error=str(e)
            )


def build_project_assigner(cfg: ProjectConfig) -> ProjectAssigner:
    if not cfg.enabled:
        return NoopProjectAssigner()
    return GitHubProjectAssigner(cfg)
