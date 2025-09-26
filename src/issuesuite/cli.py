"""IssueSuite CLI (standalone / extraction-ready).

Subcommands:
  validate  -> (placeholder) structural checks (id pattern etc.)
  sync      -> create/update/close issues (summary JSON)
  export    -> export parsed issues list to JSON
  summary   -> human-readable quick listing
  schema    -> write JSON Schemas for export & summary

Designed to be dependency-light; heavy validation can be layered externally.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import SuiteConfig, load_config
from .core import IssueSuite
from .env_auth import create_env_auth_manager
from .orchestrator import sync_with_summary

CONFIG_DEFAULT = 'issue_suite.config.yaml'


def _build_parser() -> argparse.ArgumentParser:
    """Construct top-level CLI parser with subcommands.

    Keep ordering stable for help output readability.
    """
    p = argparse.ArgumentParser(prog='issuesuite', description='Declarative GitHub issue automation')
    p.add_argument('--quiet', action='store_true', help='Suppress informational logging (env: ISSUESUITE_QUIET=1)')
    sub = p.add_subparsers(dest='cmd', required=True)

    ps = sub.add_parser('sync', help='Sync issues to GitHub (create/update/close)')
    ps.add_argument('--config', default=CONFIG_DEFAULT)
    ps.add_argument('--update', action='store_true')
    ps.add_argument('--dry-run', action='store_true')
    ps.add_argument('--respect-status', action='store_true')
    ps.add_argument('--preflight', action='store_true')
    ps.add_argument('--summary-json')

    pe = sub.add_parser('export', help='Export issues to JSON')
    pe.add_argument('--config', default=CONFIG_DEFAULT)
    pe.add_argument('--output')
    pe.add_argument('--pretty', action='store_true')

    psm = sub.add_parser('summary', help='Quick summary of parsed specs')
    psm.add_argument('--config', default=CONFIG_DEFAULT)
    psm.add_argument('--limit', type=int, default=20)

    aictx = sub.add_parser('ai-context', help='Emit machine-readable context JSON for AI tooling')
    aictx.add_argument('--config', default=CONFIG_DEFAULT)
    aictx.add_argument('--output', help='Output file (defaults to stdout)')
    aictx.add_argument('--preview', type=int, default=5, help='Preview first N specs')
    aictx.add_argument('--quiet', action='store_true', help='Suppress informational logging (env: ISSUESUITE_QUIET=1)')


    sch = sub.add_parser('schema', help='Emit JSON Schema files')
    sch.add_argument('--config', default=CONFIG_DEFAULT)
    sch.add_argument('--stdout', action='store_true')

    val = sub.add_parser('validate', help='Basic parse + id pattern validation')
    val.add_argument('--config', default=CONFIG_DEFAULT)


    # Setup command for VS Code and online integration
    setup = sub.add_parser('setup', help='Setup authentication and VS Code integration')
    setup.add_argument('--create-env', action='store_true', help='Create sample .env file')
    setup.add_argument('--check-auth', action='store_true', help='Check authentication status')
    setup.add_argument('--vscode', action='store_true', help='Setup VS Code integration files')
    setup.add_argument('--config', default=CONFIG_DEFAULT)

    return p


def _load_cfg(path: str) -> SuiteConfig:
    return load_config(path)


def _cmd_export(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    suite = IssueSuite(cfg)
    specs = suite.parse()
    data: list[dict[str, object]] = [
        {
            'external_id': s.external_id,
            'title': s.title,
            'labels': s.labels,
            'milestone': s.milestone,
            'status': s.status,
            'hash': s.hash,
            'body': s.body,
        } for s in specs
    ]
    out_path = Path(args.output or cfg.export_json)
    out_path.write_text(json.dumps(data, indent=2 if args.pretty else None) + ('\n' if args.pretty else ''))
    print(f'[export] {len(data)} issues -> {out_path}')
    return 0


def _cmd_summary(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    suite = IssueSuite(cfg)
    specs = suite.parse()
    print(f'Total: {len(specs)}')
    if os.environ.get('ISSUESUITE_AI_MODE') == '1':
        # Include both hyphen and underscore style tokens so tests / tools can detect reliably
        print('[ai-mode] ai_mode=1 dry_run=True (forced)')
    for s in specs[:args.limit]:
        print(f'  {s.external_id} {s.hash} {s.title[:70]}')
    if len(specs) > args.limit:
        print(f'  ... ({len(specs)-args.limit} more)')
    return 0


def _cmd_sync(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    summary = sync_with_summary(
        cfg,
        dry_run=args.dry_run,
        update=args.update,
        respect_status=args.respect_status,
        preflight=args.preflight,
        summary_path=args.summary_json,
    )
    print('[sync] totals', json.dumps(summary['totals']))
    return 0


def _schemas() -> dict[str, dict[str, object]]:
    export_schema: dict[str, object] = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'title': 'IssueExport',
        'type': 'array',
        'items': {'type': 'object'},
    }
    summary_schema: dict[str, object] = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'title': 'IssueChangeSummary',
        'type': 'object',
        'required': ['schemaVersion','generated_at','dry_run','totals','changes'],
    }
    return {'export': export_schema, 'summary': summary_schema}


def _cmd_schema(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    schemas = _schemas()
    if args.stdout:
        print(json.dumps(schemas, indent=2))
        return 0
    try:
        Path(cfg.schema_export_file).write_text(json.dumps(schemas['export'], indent=2) + '\n')
        Path(cfg.schema_summary_file).write_text(json.dumps(schemas['summary'], indent=2) + '\n')
        print(f"[schema] wrote {cfg.schema_export_file}, {cfg.schema_summary_file}")
        return 0
    except Exception as e:  # pragma: no cover - rare filesystem error
        print(f"[schema] ERROR: {e}", file=sys.stderr)
        return 2


def _print_lines(lines: Iterable[str]) -> None:
    for line in lines:
        print(line)


def _setup_create_env(auth_manager: Any) -> None:  # auth manager is dynamic, keep Any
    auth_manager.create_sample_env_file()
    _print_lines(["[setup] Created sample .env file"])


def _setup_check_auth(auth_manager: Any) -> None:  # dynamic methods accessed reflectively
    token = auth_manager.get_github_token()
    app_cfg = auth_manager.get_github_app_config()
    online = auth_manager.is_online_environment()
    _print_lines([
        f"[setup] Environment: {'Online' if online else 'Local'}",
        f"[setup] GitHub Token: {'✓ Found' if token else '✗ Not found'}",
        f"[setup] GitHub App: {'✓ Configured' if all(app_cfg.values()) else '✗ Not configured'}",
    ])
    recs = auth_manager.get_authentication_recommendations()
    if recs:
        print("[setup] Recommendations:")
        for rec in recs:
            print(f"  - {rec}")


def _setup_vscode() -> None:
    vscode_dir = Path('.vscode')
    if vscode_dir.exists():
        print("[setup] VS Code integration files already exist in .vscode/")
    else:
        print("[setup] Creating VS Code integration files...")
        print("[setup] VS Code files should be committed to your repository")
    _print_lines([
        "[setup] VS Code integration includes:",
        "  - Tasks for common IssueSuite operations",
        "  - Debug configurations",
        "  - YAML schema associations for config files",
        "  - Python environment configuration",
    ])


def _setup_show_help() -> None:
    _print_lines([
        "[setup] Use --help to see available setup options",
        "Available options:",
        "  --create-env    Create sample .env file",
        "  --check-auth    Check authentication status",
        "  --vscode        Setup VS Code integration",
    ])


def _cmd_setup(args: argparse.Namespace) -> int:
    auth_manager = create_env_auth_manager()
    if args.create_env:
        _setup_create_env(auth_manager)
    if args.check_auth:
        _setup_check_auth(auth_manager)
    if args.vscode:
        _setup_vscode()
    if not any([args.create_env, args.check_auth, args.vscode]):
        _setup_show_help()
    return 0


class _QuietLogs:
    """Context manager to silence 'issuesuite' logger for clean machine-readable output."""
    def __enter__(self) -> _QuietLogs:  # noqa: D401
        self._logger = logging.getLogger('issuesuite')
        self._prev_level = self._logger.level
        self._prev_handlers = list(self._logger.handlers)
        self._logger.handlers = []
        self._logger.propagate = False
        self._logger.setLevel(logging.CRITICAL + 10)
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any | None) -> None:  # noqa: D401
        self._logger.setLevel(self._prev_level)
        self._logger.handlers = self._prev_handlers
        self._logger.propagate = True


def _cmd_validate(cfg: SuiteConfig) -> int:
    suite = IssueSuite(cfg)
    specs = suite.parse()
    print(f'[validate] parsed {len(specs)} specs')
    # minimal id pattern check
    bad = [s.external_id for s in specs if not re.match(cfg.id_pattern, s.external_id)]
    if bad:
        print(f'[validate] invalid ids: {bad}', file=sys.stderr)
        return 1
    print('[validate] ok')
    return 0


def _cmd_ai_context(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    """Emit a JSON document summarizing current IssueSuite state for AI assistants."""
    quiet = args.quiet or os.environ.get('ISSUESUITE_QUIET') == '1'
    if quiet:
        with _QuietLogs():
            suite = IssueSuite(cfg)
            specs = suite.parse()
    else:
        suite = IssueSuite(cfg)
        specs = suite.parse()
    ai_mode = os.environ.get('ISSUESUITE_AI_MODE') == '1'
    mock_mode = os.environ.get('ISSUES_SUITE_MOCK') == '1'
    debug = os.environ.get('ISSUESUITE_DEBUG') == '1'
    preview_specs: list[dict[str, object]] = []
    for s in specs[:args.preview]:
        preview_specs.append({
            'external_id': s.external_id,
            'title': s.title,
            'hash': s.hash,
            'labels': s.labels,
            'milestone': s.milestone,
            'status': s.status,
        })
    safe_sync = f'issuesuite sync --dry-run --update --config {args.config}'
    if ai_mode:
        safe_sync += '  # AI mode forces dry-run'
    doc: dict[str, object] = {
        'schemaVersion': 'ai-context/1',
        'type': 'issuesuite.ai-context',
        'spec_count': len(specs),
        'preview': preview_specs,
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
        # Project integration metadata (optional, non-breaking addition)
        'project': {
            'enabled': getattr(cfg, 'project_enable', False),
            'number': getattr(cfg, 'project_number', None),
            'field_mappings': getattr(cfg, 'project_field_mappings', {}) or {},
            'has_mappings': bool(getattr(cfg, 'project_field_mappings', {}) or {}),
        },
        'recommended': {
            'safe_sync': safe_sync,
            'export': f'issuesuite export --config {args.config} --pretty',
            'summary': f'issuesuite summary --config {args.config}',
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
    out_text = json.dumps(doc, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(out_text)
    else:
        # Write directly to stdout without extra logging
        sys.stdout.write(out_text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Global quiet env fallback
    if not getattr(args, 'quiet', False) and os.environ.get('ISSUESUITE_QUIET') == '1':
        args.quiet = True  # type: ignore[attr-defined]
    cfg = _load_cfg(args.config)
    if args.cmd == 'export':
        return _cmd_export(cfg, args)
    if args.cmd == 'summary':
        return _cmd_summary(cfg, args)
    if args.cmd == 'sync':
        return _cmd_sync(cfg, args)
    if args.cmd == 'ai-context':
        return _cmd_ai_context(cfg, args)
    if args.cmd == 'schema':
        return _cmd_schema(cfg, args)
    if args.cmd == 'validate':
        return _cmd_validate(cfg)
    if args.cmd == 'setup':
        return _cmd_setup(args)
    parser.print_help()
    return 1


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
