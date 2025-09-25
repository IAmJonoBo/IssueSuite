from __future__ import annotations
import re
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

DEFAULT_MILESTONES = [
    'Sprint 0: Mobilize & Baseline',
    'M1: Real-Time Foundation',
    'M2: Performance & Validation',
    'M3: Advanced Analytics'
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
    milestone_pattern: Optional[str]
    github_repo: Optional[str]
    project_enable: bool
    project_number: Optional[int]
    project_field_mappings: Dict[str, str]
    inject_labels: List[str]
    ensure_milestones_list: List[str]
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
    github_app_id: Optional[str]
    github_app_private_key_path: Optional[str]
    github_app_installation_id: Optional[str]


def load_config(path: str | Path) -> SuiteConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f'Configuration file not found: {p}')
    if yaml is None:
        raise ConfigError('PyYAML not installed; pip install PyYAML')
    raw = yaml.safe_load(p.read_text()) or {}
    src = raw.get('source', {})
    gh = raw.get('github', {})
    defaults = raw.get('defaults', {})
    out = raw.get('output', {})
    behavior = raw.get('behavior', {})
    ai = raw.get('ai', {})
    project = gh.get('project', {}) or {}
    logging_config = raw.get('logging', {})
    performance_config = raw.get('performance', {})
    concurrency_config = raw.get('concurrency', {})
    github_app = gh.get('app', {}) or {}
    return SuiteConfig(
        version=int(raw.get('version', 1)),
        source_file=p.parent / src.get('file', 'ISSUES.md'),
        id_pattern=src.get('id_pattern', '^[0-9]{3}$'),
        milestone_required=bool(src.get('milestone_required', True)),
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
        hash_state_file=out.get('hash_state_file', '.issues_sync_state.json'),
        mapping_file=out.get('mapping_file', 'issues_mapping.json'),
        lock_file=behavior.get('lock_file', '.issues_sync.lock'),
        truncate_body_diff=int(behavior.get('truncate_body_diff', 80)),
        dry_run_default=bool(behavior.get('dry_run_default', False)),
        emit_change_events=bool(ai.get('emit_change_events', True)),
        schema_export_file=ai.get('schema_export_file', 'issue_export.schema.json'),
        schema_summary_file=ai.get('schema_summary_file', 'issue_change_summary.schema.json'),
        schema_version=int(ai.get('schema_version', 1)),
        # Logging configuration
        logging_json_enabled=bool(logging_config.get('json_enabled', False)),
        logging_level=logging_config.get('level', 'INFO'),
        # Performance configuration
        performance_benchmarking=bool(performance_config.get('benchmarking', False)),
        # Concurrency configuration
        concurrency_enabled=bool(concurrency_config.get('enabled', False)),
        concurrency_max_workers=int(concurrency_config.get('max_workers', 4)),
        # GitHub App configuration
        github_app_enabled=bool(github_app.get('enabled', False)),
        github_app_id=github_app.get('app_id'),
        github_app_private_key_path=github_app.get('private_key_path'),
        github_app_installation_id=github_app.get('installation_id'),
    )
