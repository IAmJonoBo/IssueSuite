"""IssueSuite CLI (standalone / extraction-ready).

Subcommands:
  validate  -> (placeholder) structural checks (id pattern etc.)
  sync      -> create/update/close issues (summary JSON)
  export    -> export parsed issues list to JSON
  summary   -> human-readable quick listing
  schema    -> write JSON Schemas for export & summary
    import    -> generate draft ISSUES.md from live repository issues
    reconcile -> compare live issues against local specs (no mutation)
        agent-apply -> apply agent completion summaries to ISSUES.md and docs

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
from typing import Any, cast

from . import schemas as schema_module
from .agent_updates import apply_agent_updates
from .ai_context import get_ai_context
from .config import SuiteConfig, load_config
from .core import IssueSuite
from .env_auth import create_env_auth_manager
from .github_issues import IssuesClient, IssuesClientConfig
from .orchestrator import sync_with_summary
from .parser import render_issue_block
from .reconcile import format_report, reconcile

CONFIG_DEFAULT = 'issue_suite.config.yaml'
REPO_HELP = 'Override target repository (owner/repo)'


def _build_parser() -> argparse.ArgumentParser:
    """Construct top-level CLI parser with subcommands.

    Keep ordering stable for help output readability.
    """
    p = argparse.ArgumentParser(
        prog='issuesuite', description='Declarative GitHub issue automation'
    )
    p.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress informational logging (env: ISSUESUITE_QUIET=1)',
    )
    sub = p.add_subparsers(dest='cmd', required=True)

    ps = sub.add_parser('sync', help='Sync issues to GitHub (create/update/close)')
    ps.add_argument('--config', default=CONFIG_DEFAULT)
    ps.add_argument('--repo', help=REPO_HELP)
    ps.add_argument('--update', action='store_true')
    ps.add_argument('--apply', action='store_true', help='Alias for --update (creates/updates)')
    ps.add_argument('--dry-run', action='store_true')
    ps.add_argument('--respect-status', action='store_true')
    ps.add_argument('--preflight', action='store_true')
    ps.add_argument('--summary-json')
    ps.add_argument(
        '--plan-json', help='When used with --dry-run, writes only the plan actions to a JSON file'
    )
    ps.add_argument(
        '--prune', action='store_true', help='Close issues not present in specs (removed)'
    )
    ps.add_argument('--project-owner', help='Override project owner (for future GraphQL)')
    ps.add_argument('--project-number', type=int, help='Override project number')

    pe = sub.add_parser('export', help='Export issues to JSON')
    pe.add_argument('--config', default=CONFIG_DEFAULT)
    pe.add_argument('--repo', help=REPO_HELP)
    pe.add_argument('--output')
    pe.add_argument('--pretty', action='store_true')

    psm = sub.add_parser('summary', help='Quick summary of parsed specs')
    psm.add_argument('--config', default=CONFIG_DEFAULT)
    psm.add_argument('--repo', help=REPO_HELP)
    psm.add_argument('--limit', type=int, default=20)

    imp = sub.add_parser('import', help='Generate draft ISSUES.md from live issues')
    imp.add_argument('--config', default=CONFIG_DEFAULT)
    imp.add_argument('--repo', help=REPO_HELP)
    imp.add_argument(
        '--output',
        default='ISSUES.import.md',
        help='Output markdown file (default: ISSUES.import.md)',
    )
    imp.add_argument('--limit', type=int, default=500, help='Max issues to import (default 500)')

    rec = sub.add_parser('reconcile', help='Detect drift between local specs and live issues')
    rec.add_argument('--config', default=CONFIG_DEFAULT)
    rec.add_argument('--repo', help=REPO_HELP)
    rec.add_argument(
        '--limit', type=int, default=500, help='Max issues to fetch for comparison (default 500)'
    )

    doc = sub.add_parser('doctor', help='Run diagnostics (auth, repo access, config)')
    doc.add_argument('--config', default=CONFIG_DEFAULT)
    doc.add_argument('--repo', help=REPO_HELP)

    aictx = sub.add_parser('ai-context', help='Emit machine-readable context JSON for AI tooling')
    aictx.add_argument('--config', default=CONFIG_DEFAULT)
    aictx.add_argument('--repo', help=REPO_HELP)
    aictx.add_argument('--output', help='Output file (defaults to stdout)')
    aictx.add_argument('--preview', type=int, default=5, help='Preview first N specs')
    aictx.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress informational logging (env: ISSUESUITE_QUIET=1)',
    )

    sch = sub.add_parser('schema', help='Emit JSON Schema files')
    sch.add_argument('--config', default=CONFIG_DEFAULT)
    sch.add_argument('--repo', help=REPO_HELP)
    sch.add_argument('--stdout', action='store_true')

    val = sub.add_parser('validate', help='Basic parse + id pattern validation')
    val.add_argument('--config', default=CONFIG_DEFAULT)
    val.add_argument('--repo', help=REPO_HELP)

    # Agent updates subcommand: ingest completion summaries and update ISSUES.md/docs
    au = sub.add_parser(
        'agent-apply',
        help='Apply agent completion summaries to ISSUES.md and optional docs, then sync',
    )
    au.add_argument('--config', default=CONFIG_DEFAULT)
    au.add_argument('--updates-json', help='Path to JSON file with agent updates (default: stdin)')
    au.add_argument('--apply', action='store_true', help='Perform GitHub mutations (sync apply)')
    au.add_argument(
        '--no-sync', action='store_true', help='Do not run sync after applying file updates'
    )
    au.add_argument(
        '--respect-status',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Respect status for closing issues (default: true; use --no-respect-status to disable)',
    )
    au.add_argument(
        '--dry-run-sync',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Run a dry-run sync after file updates (default: true when --apply is not used; otherwise false unless explicitly enabled)',
    )
    au.add_argument(
        '--summary-json',
        help='Optional path to write sync summary json (passed through to sync)',
    )

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
        }
        for s in specs
    ]
    out_path = Path(args.output or cfg.export_json)
    out_path.write_text(
        json.dumps(data, indent=2 if args.pretty else None) + ('\n' if args.pretty else '')
    )
    print(f'[export] {len(data)} issues -> {out_path}')
    return 0


def _cmd_summary(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    suite = IssueSuite(cfg)
    specs = suite.parse()
    print(f'Total: {len(specs)}')
    if os.environ.get('ISSUESUITE_AI_MODE') == '1':
        # Include both hyphen and underscore style tokens so tests / tools can detect reliably
        print('[ai-mode] ai_mode=1 dry_run=True (forced)')
    for s in specs[: args.limit]:
        print(f'  {s.external_id} {s.hash} {s.title[:70]}')
    if len(specs) > args.limit:
        print(f'  ... ({len(specs) - args.limit} more)')
    return 0


def _cmd_sync(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    # Alias: --apply implies --update for ergonomics
    if getattr(args, 'apply', False) and not getattr(args, 'update', False):
        try:
            args.update = True
        except Exception:
            pass
    summary = sync_with_summary(
        cfg,
        dry_run=args.dry_run,
        update=args.update,
        respect_status=args.respect_status,
        preflight=args.preflight,
        summary_path=args.summary_json,
        prune=args.prune,
    )
    totals = summary.get('totals') if isinstance(summary, dict) else None
    if isinstance(totals, dict):
        print('[sync] totals', json.dumps(totals))
    # Optionally emit plan JSON (subset) when requested and available
    if args.dry_run and getattr(args, 'plan_json', None):
        plan = summary.get('plan') if isinstance(summary, dict) else None
        if isinstance(plan, list):
            try:
                Path(args.plan_json).write_text(json.dumps({'plan': plan}, indent=2) + '\n')
                print(f"[sync] plan -> {args.plan_json}")
            except Exception as exc:  # pragma: no cover - filesystem edge
                print(f"[sync] failed to write plan json: {exc}", file=sys.stderr)
    return 0


def _cmd_schema(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    schemas = schema_module.get_schemas()
    if args.stdout:
        print(json.dumps(schemas, indent=2))
        return 0
    try:
        Path(cfg.schema_export_file).write_text(json.dumps(schemas['export'], indent=2) + '\n')
        Path(cfg.schema_summary_file).write_text(json.dumps(schemas['summary'], indent=2) + '\n')
        if 'ai_context' in schemas and getattr(cfg, 'schema_ai_context_file', None):
            Path(cfg.schema_ai_context_file).write_text(
                json.dumps(schemas['ai_context'], indent=2) + '\n'
            )
            print(
                f"[schema] wrote {cfg.schema_export_file}, {cfg.schema_summary_file}, {cfg.schema_ai_context_file}"
            )
        else:
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
    _print_lines(
        [
            f"[setup] Environment: {'Online' if online else 'Local'}",
            f"[setup] GitHub Token: {'✓ Found' if token else '✗ Not found'}",
            f"[setup] GitHub App: {'✓ Configured' if all(app_cfg.values()) else '✗ Not configured'}",
        ]
    )
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
    _print_lines(
        [
            "[setup] VS Code integration includes:",
            "  - Tasks for common IssueSuite operations",
            "  - Debug configurations",
            "  - YAML schema associations for config files",
            "  - Python environment configuration",
        ]
    )


def _setup_show_help() -> None:
    _print_lines(
        [
            "[setup] Use --help to see available setup options",
            "Available options:",
            "  --create-env    Create sample .env file",
            "  --check-auth    Check authentication status",
            "  --vscode        Setup VS Code integration",
        ]
    )


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

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any | None
    ) -> None:  # noqa: D401
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
    # Leverage shared library function for single source of truth
    doc = get_ai_context(cfg, preview=args.preview)
    out_text = json.dumps(doc, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(out_text)
    else:
        sys.stdout.write(out_text)
    return 0


def _read_updates_json(path: str | None) -> dict[str, Any] | list[dict[str, Any]]:
    if path:
        text = Path(path).read_text(encoding='utf-8')
    else:
        text = sys.stdin.read()
    data: Any = json.loads(text)
    # Accept dict or list
    if isinstance(data, dict):
        return cast(dict[str, Any], data)
    if isinstance(data, list):
        return cast(list[dict[str, Any]], data)
    raise ValueError('updates json must be a dict or list')


def _cmd_agent_apply(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    # Load updates data
    try:
        updates_data = _read_updates_json(args.updates_json)
    except Exception as exc:
        print(f"[agent-apply] failed to read updates: {exc}", file=sys.stderr)
        return 2

    # Apply updates to ISSUES.md and docs
    try:
        result = apply_agent_updates(cfg, updates_data)
    except Exception as exc:
        print(f"[agent-apply] failed to apply updates: {exc}", file=sys.stderr)
        return 2

    changed_files = result.get('changed_files', []) if isinstance(result, dict) else []
    print(f"[agent-apply] updated files: {', '.join(changed_files) if changed_files else 'none'}")

    # Optionally run sync
    if not args.no_sync:
        do_apply = bool(args.apply)
        # Default behavior: respect status when agent applies (closes issues)
        respect_status = bool(getattr(args, 'respect_status', True))
        dry_run = not do_apply or bool(args.dry_run_sync)
        try:
            summary = sync_with_summary(
                cfg,
                dry_run=dry_run,
                update=True,
                respect_status=respect_status,
                preflight=False,
                summary_path=args.summary_json,
                prune=False,
            )
            totals = summary.get('totals') if isinstance(summary, dict) else None
            if isinstance(totals, dict):
                print('[agent-apply] sync totals', json.dumps(totals))
        except Exception as exc:
            print(f"[agent-apply] sync failed: {exc}", file=sys.stderr)
            return 2
    return 0


def _slugify(title: str) -> str:
    base = re.sub(r'[^a-zA-Z0-9-_]+', '-', title.strip().lower()).strip('-')
    if not base:
        base = 'issue'
    return base[:50]


def _extract_issue_fields(it: dict[str, Any]) -> tuple[str, str, list[str], str | None, str | None]:
    title = str(it.get('title') or '').strip() or 'Untitled'
    body = str(it.get('body') or '').strip()
    labels_raw: list[str] = []
    for lbl in it.get('labels') or []:
        if isinstance(lbl, dict):
            name = lbl.get('name')
            if isinstance(name, str) and name:
                labels_raw.append(name)
    ms = it.get('milestone')
    milestone_title = (
        ms.get('title') if isinstance(ms, dict) and isinstance(ms.get('title'), str) else None
    )
    state_val = str(it.get('state') or '').lower()
    status = state_val if state_val in {'open', 'closed'} else None
    return title, body, labels_raw, milestone_title, status


def _render_issue_block(
    slug: str, title: str, body: str, labels: list[str], milestone: str | None, status: str | None
) -> list[str]:
    # Preserve import-time trimming but use shared renderer for formatting
    trimmed = re.sub(r'<!--\s*issuesuite:slug=[^>]+-->\s*', '', body)[:400].replace('```', '`\n`')
    if trimmed and not trimmed.endswith('\n'):
        trimmed += '\n'
    return render_issue_block(
        slug=slug,
        title=title,
        labels=labels or None,
        milestone=milestone,
        status=status,
        body=trimmed,
    )


def _cmd_import(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    client_cfg = IssuesClientConfig(
        repo=args.repo or cfg.github_repo,
        dry_run=False,
        mock=os.environ.get('ISSUES_SUITE_MOCK') == '1',
    )
    client = IssuesClient(client_cfg)
    issues = client.list_existing()
    if not issues:
        print('[import] no issues fetched (empty or auth problem)')
        return 1
    lines: list[str] = []
    count = 0
    seen_slugs: set[str] = set()
    for it in issues:
        if count >= args.limit:
            break
        title, body, labels_list, milestone_title, status = _extract_issue_fields(it)
        slug = _slugify(title)
        base = slug
        idx = 2
        while slug in seen_slugs:
            slug = f'{base}-{idx}'
            idx += 1
        seen_slugs.add(slug)
        lines.extend(_render_issue_block(slug, title, body, labels_list, milestone_title, status))
        count += 1
    out_path = Path(args.output)
    out_path.write_text('\n'.join(lines).rstrip() + '\n')
    print(f'[import] wrote {count} issues -> {out_path}')
    if count < len(issues):
        print(f'[import] (truncated to {count} of {len(issues)})')
    return 0


def _cmd_reconcile(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    # Parse local specs
    suite = IssueSuite(cfg)
    try:
        specs = suite.parse()
    except Exception as exc:  # pragma: no cover - parse error path
        print(f"[reconcile] failed to parse specs: {exc}", file=sys.stderr)
        return 2
    # Fetch live issues (respect mock & dry-run semantics by using IssuesClient directly)
    client = IssuesClient(
        IssuesClientConfig(
            repo=args.repo or cfg.github_repo,
            dry_run=False,
            mock=os.environ.get('ISSUES_SUITE_MOCK') == '1',
        )
    )
    live = client.list_existing()[: args.limit]
    rep = reconcile(specs=specs, live_issues=live)
    for line in format_report(rep):
        print(line)
    return 0 if bool(rep.get('in_sync')) else 2


def _doctor_repo_check(repo: str | None, problems: list[str]) -> None:
    print(f"[doctor] repo: {repo or 'None'}")
    if not repo:
        problems.append('No repository configured (github_repo)')


def _doctor_token_check(warnings: list[str]) -> None:
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    print(f"[doctor] token: {'present' if token else 'missing'}")
    if not token:
        warnings.append(
            'No GH_TOKEN/GITHUB_TOKEN environment variable detected (may rely on gh auth)'
        )


def _doctor_env_flags() -> tuple[bool, bool]:
    mock = os.environ.get('ISSUES_SUITE_MOCK') == '1'
    dry = os.environ.get('ISSUESUITE_DRY_FORCE') == '1'
    if mock:
        print('[doctor] mock mode detected (ISSUES_SUITE_MOCK=1)')
    if dry:
        print('[doctor] global dry-run override (ISSUESUITE_DRY_FORCE=1)')
    return mock, dry


def _doctor_issue_list(repo: str | None, mock: bool, problems: list[str]) -> None:
    if repo and not mock:
        try:
            client = IssuesClient(IssuesClientConfig(repo=repo, dry_run=False, mock=False))
            issues = client.list_existing()
            print(f"[doctor] list_existing ok: fetched {len(issues)} issues")
        except Exception as exc:  # pragma: no cover - external env dependent
            problems.append(f'Failed to list issues: {exc}')


def _doctor_emit_results(warnings: list[str], problems: list[str]) -> int:
    if warnings:
        print('[doctor] warnings:')
        for w in warnings:
            print(f'  - {w}')
    if problems:
        print('[doctor] problems:')
        for p in problems:
            print(f'  - {p}')
        return 2
    print('[doctor] ok')
    return 0


def _cmd_doctor(cfg: SuiteConfig, args: argparse.Namespace) -> int:
    """Run lightweight diagnostics (auth, repo access, env flags)."""
    problems: list[str] = []
    warnings: list[str] = []
    repo = args.repo or cfg.github_repo
    _doctor_repo_check(repo, problems)
    _doctor_token_check(warnings)
    mock, _ = _doctor_env_flags()
    _doctor_issue_list(repo, mock, problems)
    return _doctor_emit_results(warnings, problems)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Global quiet env fallback
    if not getattr(args, 'quiet', False) and os.environ.get('ISSUESUITE_QUIET') == '1':
        args.quiet = True
    cfg = _load_cfg(args.config)
    # Apply repo override if provided
    if getattr(args, 'repo', None):
        # SuiteConfig is a dataclass; mutate attribute directly (safe for ephemeral CLI use)
        cfg.github_repo = args.repo
    # Apply project number override (sync only for now)
    if args.cmd == 'sync' and getattr(args, 'project_number', None) is not None:
        try:
            pn = int(args.project_number)
            if pn > 0:
                cfg.project_number = pn
                cfg.project_enable = True  # ensure project logic executes if user supplies it
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
    # Dispatch table to reduce branching complexity
    handlers: dict[str, Any] = {
        'export': lambda: _cmd_export(cfg, args),
        'summary': lambda: _cmd_summary(cfg, args),
        'sync': lambda: _cmd_sync(cfg, args),
        'ai-context': lambda: _cmd_ai_context(cfg, args),
        'agent-apply': lambda: _cmd_agent_apply(cfg, args),
        'schema': lambda: _cmd_schema(cfg, args),
        'validate': lambda: _cmd_validate(cfg),
        'setup': lambda: _cmd_setup(args),
        'import': lambda: _cmd_import(cfg, args),
        'reconcile': lambda: _cmd_reconcile(cfg, args),
        'doctor': lambda: _cmd_doctor(cfg, args),
    }
    handler = handlers.get(args.cmd)
    if handler is None:  # pragma: no cover - argparse enforces valid choices
        parser.print_help()
        return 1
    return int(handler())


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
