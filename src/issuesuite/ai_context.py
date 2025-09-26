from __future__ import annotations

import os
from typing import Any

from .config import SuiteConfig
from .context_types import AIContextDoc
from .core import IssueSuite
from .mapping_utils import MAPPING_SNAPSHOT_THRESHOLD, load_mapping_snapshot


def get_ai_context(cfg: SuiteConfig, *, preview: int = 5) -> AIContextDoc:
    """Programmatic equivalent of the `ai-context` CLI command."""
    suite = IssueSuite(cfg)
    specs = suite.parse()
    ai_mode = os.environ.get('ISSUESUITE_AI_MODE') == '1'
    mock_mode = os.environ.get('ISSUES_SUITE_MOCK') == '1'
    debug = os.environ.get('ISSUESUITE_DEBUG') == '1'

    preview_specs: list[dict[str, Any]] = [
        {
            'external_id': s.external_id,
            'title': s.title,
            'hash': s.hash,
            'labels': s.labels,
            'milestone': s.milestone,
            'status': s.status,
        }
        for s in specs[:preview]
    ]
    safe_sync = 'issuesuite sync --dry-run --update --config issue_suite.config.yaml'
    if ai_mode:
        safe_sync += '  # AI mode forces dry-run'
    mapping_snapshot = load_mapping_snapshot(cfg)
    doc: AIContextDoc = {
        'schemaVersion': 'ai-context/1',
        'type': 'issuesuite.ai-context',
        'spec_count': len(specs),
        'preview': preview_specs,
        'errors': {
            'categories': [
                'github.rate_limit',
                'github.abuse',
                'network',
                'parse',
                'generic'
            ],
            'retry': {
                'attempts_env': os.environ.get('ISSUESUITE_RETRY_ATTEMPTS', '3'),
                'base_env': os.environ.get('ISSUESUITE_RETRY_BASE', '0.5'),
                'strategy': 'exponential_backoff_with_jitter'
            }
        },
        'mapping': {
            'present': bool(mapping_snapshot),
            'size': len(mapping_snapshot),
            'snapshot_included': bool(mapping_snapshot) and len(mapping_snapshot) <= MAPPING_SNAPSHOT_THRESHOLD,
            'snapshot': mapping_snapshot if mapping_snapshot and len(mapping_snapshot) <= MAPPING_SNAPSHOT_THRESHOLD else None,
        },
        'config': {
            'dry_run_default': cfg.dry_run_default,
            'ensure_labels_enabled': cfg.ensure_labels_enabled,
            'ensure_milestones_enabled': cfg.ensure_milestones_enabled,
            'truncate_body_diff': cfg.truncate_body_diff,
            'concurrency_enabled': cfg.concurrency_enabled,
            'concurrency_max_workers': cfg.concurrency_max_workers,
            'performance_benchmarking': cfg.performance_benchmarking,
        },
        'env': {
            'ai_mode': ai_mode,
            'mock_mode': mock_mode,
            'debug_logging': debug,
        },
        'project': {
            'enabled': getattr(cfg, 'project_enable', False),
            'number': getattr(cfg, 'project_number', None),
            'field_mappings': getattr(cfg, 'project_field_mappings', {}) or {},
            'has_mappings': bool(getattr(cfg, 'project_field_mappings', {}) or {}),
        },
        'recommended': {
            'safe_sync': safe_sync,
            'export': 'issuesuite export --config issue_suite.config.yaml --pretty',
            'summary': 'issuesuite summary --config issue_suite.config.yaml',
            'usage': [
                'Use safe_sync for read-only diffing in AI mode',
                'Call export for full structured spec list when preview insufficient',
                'Prefer summary for quick human-readable validation before sync'
            ],
            'env': [
                'ISSUESUITE_AI_MODE=1 to force dry-run safety',
                'ISSUES_SUITE_MOCK=1 for offline parsing without GitHub API',
                'ISSUESUITE_DEBUG=1 for verbose debugging output'
            ],
        }
    }
    return doc

__all__ = ["get_ai_context"]
