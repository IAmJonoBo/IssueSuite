from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = cast(Any, None)

from .schema_registry import get_schema_descriptor

DEFAULT_MILESTONES = [
    'Sprint 0: Mobilize & Baseline',
    'M1: Real-Time Foundation',
    'M2: Performance & Validation',
    'M3: Advanced Analytics',
]


class ConfigError(RuntimeError):
    pass


@dataclass
class SuiteConfig:
    version: int
    source_file: Path
    id_pattern: str
    milestone_required: bool
    auto_status_label: bool
    milestone_pattern: str | None
    github_repo: str | None
    project_enable: bool
    project_number: int | None
    project_field_mappings: dict[str, str]
    inject_labels: list[str]
    ensure_milestones_list: list[str]
    ensure_labels_enabled: bool
    ensure_milestones_enabled: bool
    summary_json: str
    export_json: str
    report_html: str
    hash_state_file: str
    mapping_file: str
    lock_file: str
    truncate_body_diff: int
    dry_run_default: bool
    emit_change_events: bool
    schema_export_file: str
    schema_summary_file: str
    schema_ai_context_file: str
    schema_version: int
    # Logging configuration
    logging_json_enabled: bool
    logging_level: str
    # Performance configuration
    performance_benchmarking: bool
    # Concurrency configuration
    concurrency_enabled: bool
    concurrency_max_workers: int
    # GitHub App configuration
    github_app_enabled: bool
    github_app_id: str | None
    github_app_private_key_path: str | None
    github_app_installation_id: str | None
    # Environment authentication configuration
    env_auth_enabled: bool
    env_auth_load_dotenv: bool
    env_auth_dotenv_path: str | None


def _resolve_env_var(value: Any, env_var_name: str | None = None) -> Any:
    """Resolve environment variable if value starts with $."""
    if isinstance(value, str) and value.startswith('$'):
        env_name = env_var_name or value[1:]  # Remove $ prefix
        return os.getenv(env_name, value)  # Fallback to original if not found
    return value


def load_config(path: str | Path) -> SuiteConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f'Configuration file not found: {p}')
    if yaml is None:
        raise ConfigError('PyYAML not installed; pip install PyYAML')
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text()) or {})
    src = cast(dict[str, Any], raw.get('source', {}) or {})
    gh = cast(dict[str, Any], raw.get('github', {}) or {})
    defaults = cast(dict[str, Any], raw.get('defaults', {}) or {})
    out = cast(dict[str, Any], raw.get('output', {}) or {})
    behavior = cast(dict[str, Any], raw.get('behavior', {}) or {})
    ai = cast(dict[str, Any], raw.get('ai', {}) or {})
    project = cast(dict[str, Any], gh.get('project', {}) or {})
    logging_config = cast(dict[str, Any], raw.get('logging', {}) or {})
    performance_config = cast(dict[str, Any], raw.get('performance', {}) or {})
    concurrency_config = cast(dict[str, Any], raw.get('concurrency', {}) or {})
    github_app = cast(dict[str, Any], gh.get('app', {}) or {})
    env_auth = cast(dict[str, Any], raw.get('environment', {}) or {})

    # Resolve environment variables in GitHub App configuration
    github_app_id = _resolve_env_var(github_app.get('app_id'), 'GITHUB_APP_ID')
    github_app_private_key_path = _resolve_env_var(
        github_app.get('private_key_path'), 'GITHUB_APP_PRIVATE_KEY'
    )
    github_app_installation_id = _resolve_env_var(
        github_app.get('installation_id'), 'GITHUB_APP_INSTALLATION_ID'
    )

    summary_version = int(get_schema_descriptor("summary").version)

    return SuiteConfig(
        version=int(raw.get('version', 1)),
        source_file=p.parent / src.get('file', 'ISSUES.md'),
        # New slug-based format default: lowercase alnum plus hyphen/underscore
        id_pattern=src.get('id_pattern', '^[a-z0-9][a-z0-9-_]*$'),
        # Milestone enforcement is opt-in; default False to preserve backward compatibility.
        milestone_required=bool(src.get('milestone_required', False)),
        auto_status_label=bool(src.get('auto_status_label', True)),
        milestone_pattern=src.get('milestone_pattern'),
        github_repo=gh.get('repo'),
        project_enable=bool(project.get('enable', False)),
        project_number=project.get('number'),
        project_field_mappings=project.get('field_mappings', {}) or {},
        inject_labels=defaults.get('inject_labels', []) or [],
        ensure_milestones_list=defaults.get('ensure_milestones', DEFAULT_MILESTONES),
        ensure_labels_enabled=bool(defaults.get('ensure_labels_enabled', False)),
        ensure_milestones_enabled=bool(defaults.get('ensure_milestones_enabled', False)),
        summary_json=out.get('summary_json', 'issues_summary.json'),
        export_json=out.get('export_json', 'issues_export.json'),
        report_html=out.get('report_html', 'issues_report.html'),
        hash_state_file=out.get('hash_state_file', '.issuesuite_hashes.json'),
        mapping_file=out.get('mapping_file', '.issuesuite_mapping.json'),
        lock_file=out.get('lock_file', '.issuesuite_lock'),
        truncate_body_diff=int(behavior.get('truncate_body_diff', 80)),
        dry_run_default=bool(behavior.get('dry_run_default', False)),
        emit_change_events=bool(behavior.get('emit_change_events', False)),
        schema_export_file=ai.get('schema_export_file', 'issue_export.schema.json'),
        schema_summary_file=ai.get('schema_summary_file', 'issue_change_summary.schema.json'),
        schema_ai_context_file=ai.get('schema_ai_context_file', 'ai_context.schema.json'),
        schema_version=int(ai.get('schema_version', summary_version)),
        # Logging configuration
        logging_json_enabled=bool(logging_config.get('json_enabled', False)),
        logging_level=logging_config.get('level', 'INFO'),
        # Performance configuration
        performance_benchmarking=bool(performance_config.get('benchmarking', False)),
        # Concurrency configuration
        concurrency_enabled=bool(concurrency_config.get('enabled', False)),
        concurrency_max_workers=int(concurrency_config.get('max_workers', 4)),
        # GitHub App configuration with environment variable resolution
        github_app_enabled=bool(github_app.get('enabled', False)),
        github_app_id=github_app_id,
        github_app_private_key_path=github_app_private_key_path,
        github_app_installation_id=github_app_installation_id,
        # Environment authentication configuration
        env_auth_enabled=bool(env_auth.get('enabled', True)),
        env_auth_load_dotenv=bool(env_auth.get('load_dotenv', True)),
        env_auth_dotenv_path=env_auth.get('dotenv_path'),
    )
