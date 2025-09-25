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
import sys
from pathlib import Path
from typing import Any, List, Optional

from .config import load_config, SuiteConfig
from .orchestrator import sync_with_summary
from .core import IssueSuite

CONFIG_DEFAULT = 'issue_suite.config.yaml'


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='issuesuite', description='Declarative GitHub issue automation')
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

    sch = sub.add_parser('schema', help='Emit JSON Schema files')
    sch.add_argument('--config', default=CONFIG_DEFAULT)
    sch.add_argument('--stdout', action='store_true')

    val = sub.add_parser('validate', help='Basic parse + id pattern validation')
    val.add_argument('--config', default=CONFIG_DEFAULT)

    return p


def _load_cfg(path: str) -> SuiteConfig:
    return load_config(path)


def _cmd_export(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    suite = IssueSuite(cfg)
    specs = suite.parse()
    data = [
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


def _schemas() -> dict:
    export_schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'title': 'IssueExport',
        'type': 'array',
        'items': {'type': 'object'},
    }
    summary_schema = {
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


def _cmd_validate(cfg: SuiteConfig) -> int:
    suite = IssueSuite(cfg)
    specs = suite.parse()
    print(f'[validate] parsed {len(specs)} specs')
    # minimal id pattern check
    import re
    bad = [s.external_id for s in specs if not re.match(cfg.id_pattern, s.external_id)]
    if bad:
        print(f'[validate] invalid ids: {bad}', file=sys.stderr)
        return 1
    print('[validate] ok')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = _load_cfg(args.config)
    if args.cmd == 'export':
        return _cmd_export(cfg, args)
    if args.cmd == 'summary':
        return _cmd_summary(cfg, args)
    if args.cmd == 'sync':
        return _cmd_sync(cfg, args)
    if args.cmd == 'schema':
        return _cmd_schema(cfg, args)
    if args.cmd == 'validate':
        return _cmd_validate(cfg)
    parser.print_help()
    return 1


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
