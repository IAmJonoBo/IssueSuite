from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .benchmarking import BenchmarkConfig, create_benchmark
from .concurrency import (
    ConcurrencyConfig,
    create_async_github_client,
    create_concurrent_processor,
    enable_concurrency_for_large_roadmaps,
    get_optimal_worker_count,
)
from .config import SuiteConfig
from .env_auth import EnvAuthConfig, create_env_auth_manager
from .github_auth import GitHubAppConfig, create_github_app_manager
from .logging import configure_logging, get_logger
from .project import ProjectConfig, build_project_assigner

# Canonical label normalization map (mirrors legacy script)
_LABEL_CANON_MAP = {
    'p0-critical': 'P0-critical',
    'p1-important': 'P1-important',
    'p2-enhancement': 'P2-enhancement',
}

def _parse_meta_block(lines: List[str], start_index: int) -> tuple[Dict[str, str], List[str], int]:
    meta: Dict[str, str] = {}
    i = start_index
    while i < len(lines) and lines[i].strip() != '---':
        line = lines[i].strip()
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip().lower()] = v.strip()
        i += 1
    if i < len(lines) and lines[i].strip() == '---':
        i += 1
    body: List[str] = []
    while i < len(lines) and not lines[i].startswith('## '):
        body.append(lines[i])
        i += 1
    return meta, body, i

def _build_issue_spec(external_id: str, canonical_title: str, meta: Dict[str, str], body_lines: List[str]) -> tuple['IssueSpec', str]:
    import hashlib
    labels_raw = [l.strip() for l in meta.get('labels','').split(',') if l.strip()]
    labels_norm = [_LABEL_CANON_MAP.get(lbl.lower(), lbl) for lbl in labels_raw]
    body = '\n'.join(body_lines).strip() + '\n'
    title = f"Issue {external_id}: {canonical_title}"
    h = hashlib.sha256()
    h.update('\x1f'.join([
        external_id,
        canonical_title,
        ','.join(sorted(labels_norm)),
        meta.get('milestone') or '',
        meta.get('flag') or '',
        meta.get('priority') or '',
        body.strip(),
    ]).encode('utf-8'))
    issue = IssueSpec(
        external_id=external_id,
        title=title,
        labels=labels_norm,
        milestone=meta.get('milestone'),
        body=body,
        status=meta.get('status')
    )
    issue.hash = h.hexdigest()[:16]
    return issue, canonical_title

try:
    import yaml  # noqa: F401
except Exception:  # pragma: no cover
    pass

# Lightweight IssueSpec for library usage
@dataclass
class IssueSpec:
    external_id: str
    title: str
    labels: List[str]
    milestone: Optional[str]
    body: str
    status: Optional[str] = None
    hash: Optional[str] = None


class IssueSuite:
    def __init__(self, cfg: SuiteConfig):
        self.cfg = cfg
        self._debug = os.environ.get('ISSUESUITE_DEBUG') == '1'
        # Mock mode: skip all GitHub CLI invocations even in non-dry-run paths
        self._mock = os.environ.get('ISSUES_SUITE_MOCK') == '1'
        
        # Configure structured logging based on config
        self._logger = configure_logging(
            json_logging=cfg.logging_json_enabled,
            level=cfg.logging_level
        )
        
        # Configure environment authentication
        if cfg.env_auth_enabled:
            self._env_auth_manager = create_env_auth_manager(EnvAuthConfig(
                load_dotenv=cfg.env_auth_load_dotenv,
                dotenv_path=cfg.env_auth_dotenv_path
            ))
            # Setup authentication from environment
            self._setup_env_authentication()
        else:
            self._env_auth_manager = None
        
        # Configure concurrency
        self._concurrency_config = ConcurrencyConfig(
            enabled=cfg.concurrency_enabled,
            max_workers=cfg.concurrency_max_workers,
            batch_size=10  # Default batch size
        )
        
        # Configure GitHub App authentication
        self._github_app_config = GitHubAppConfig(
            enabled=cfg.github_app_enabled,
            app_id=cfg.github_app_id,
            private_key_path=cfg.github_app_private_key_path,
            installation_id=cfg.github_app_installation_id
        )
        self._github_app_manager = None
        
        # Configure performance benchmarking
        self._benchmark_config = BenchmarkConfig(
            enabled=cfg.performance_benchmarking,
            output_file='performance_report.json',
            collect_system_metrics=True,
            track_memory=True,
            track_cpu=True
        )
        self._benchmark = create_benchmark(self._benchmark_config, self._mock)
        
        # Setup GitHub App authentication if enabled
        if self._github_app_config.enabled:
            self._setup_github_app_auth()

    def _setup_env_authentication(self) -> None:
        """Setup environment-based authentication."""
        if not self._env_auth_manager:
            return
        
        try:
            # Try to configure GitHub CLI with environment token
            if self._env_auth_manager.configure_github_cli():
                self._logger.log_operation("env_auth_configured", 
                                         source="environment_variables")
            
            # Log authentication recommendations if needed
            recommendations = self._env_auth_manager.get_authentication_recommendations()
            if recommendations:
                self._logger.info("Authentication recommendations: " + "; ".join(recommendations))
            
            # Detect online environment
            if self._env_auth_manager.is_online_environment():
                self._logger.log_operation("online_environment_detected")
                
        except Exception as e:
            self._logger.log_error("Environment authentication setup failed", error=str(e))

    def _setup_github_app_auth(self) -> None:
        """Setup GitHub App authentication."""
        try:
            self._github_app_manager = create_github_app_manager(
                self._github_app_config, self._mock
            )
            
            if self._github_app_manager.is_enabled():
                success = self._github_app_manager.configure_github_cli()
                if success:
                    self._logger.log_operation("github_app_auth_configured",
                                             app_id=self._github_app_config.app_id)
                else:
                    self._logger.log_error("Failed to configure GitHub App authentication")
        except Exception as e:
            self._logger.log_error("GitHub App authentication setup failed", error=str(e))

    def _log(self, *parts: Any):  # lightweight internal debug logger
        if self._debug:
            print('[issuesuite]', *parts)
        # Also log via structured logger
        self._logger.debug(' '.join(str(p) for p in parts))

    @classmethod
    def from_config_path(cls, path: str | Path) -> 'IssueSuite':
        from .config import load_config
        return cls(load_config(path))

    def parse(self) -> List[IssueSpec]:
        import re
        section_re = re.compile(r'^##\s+(\d{3})\s*\|\s*(.+)$')
        lines = self.cfg.source_file.read_text(encoding='utf-8').splitlines()
        specs: List[IssueSpec] = []
        i = 0
        while i < len(lines):
            m = section_re.match(lines[i])
            if not m:
                i += 1
                continue
            external_id, canonical_title = m.group(1), m.group(2).strip()
            i += 1
            meta, body_lines, i = _parse_meta_block(lines, i)
            issue, _ = _build_issue_spec(external_id, canonical_title, meta, body_lines)
            specs.append(issue)
        return specs

    def sync(self, *, dry_run: bool, update: bool, respect_status: bool, preflight: bool) -> Dict[str, Any]:
        with self._benchmark.measure('sync_total', dry_run=dry_run, update=update,
                                     respect_status=respect_status, preflight=preflight), \
             self._logger.timed_operation('sync', dry_run=dry_run, update=update,
                                          respect_status=respect_status, preflight=preflight):
            self._log('sync:start', f'dry_run={dry_run}', f'update={update}', f'respect_status={respect_status}', f'preflight={preflight}')

            specs = self._sync_parse_and_preflight(preflight)
            project_assigner = self._build_project_assigner()
            existing = self._sync_fetch_existing(preflight)
            prev_hashes = self._load_hash_state()
            results = self._sync_process_specs(specs, existing, prev_hashes, dry_run, update, respect_status, project_assigner)
            summary = self._sync_build_summary(specs, results)

            if not dry_run:
                with self._benchmark.measure('save_hash_state'):
                    self._save_hash_state(specs)

            self._log('sync:done', summary['totals'])
            self._logger.log_operation('sync_complete',
                                       issues_created=summary['totals']['created'],
                                       issues_updated=summary['totals']['updated'],
                                       issues_closed=summary['totals']['closed'],
                                       specs=summary['totals']['specs'],
                                       skipped=summary['totals']['skipped'])

            if self._benchmark_config.enabled:
                self._benchmark.generate_report()
            return summary

    # --- sync refactor helpers ---
    def _sync_parse_and_preflight(self, preflight: bool) -> List[IssueSpec]:
        with self._benchmark.measure('parse_specs', spec_count='pending'):
            specs = self.parse()
        self._log('sync:parsed', len(specs), 'specs')
        self._logger.log_operation('parse_complete', spec_count=len(specs))
        if preflight:
            with self._benchmark.measure('preflight_setup'):
                self._preflight(specs)
        return specs

    def _build_project_assigner(self):
        return build_project_assigner(ProjectConfig(
            enabled=bool(getattr(self.cfg, 'project_enable', False)),
            number=getattr(self.cfg, 'project_number', None),
            field_mappings=getattr(self.cfg, 'project_field_mappings', {}) or {},
        ))

    def _sync_fetch_existing(self, preflight: bool) -> List[Dict[str, Any]]:
        with self._benchmark.measure('fetch_existing_issues'):
            if preflight and not (self.cfg.ensure_labels_enabled or self.cfg.ensure_milestones_enabled):
                existing: List[Dict[str, Any]] = []
            else:
                existing = self._existing_issues() if self._gh_auth() else []
        self._log('sync:existing_issues', len(existing))
        self._logger.log_operation('fetch_existing_issues', issue_count=len(existing))
        return existing

    def _sync_process_specs(self, specs: List[IssueSpec], existing: List[Dict[str, Any]], prev_hashes: Dict[str, str],
                            dry_run: bool, update: bool, respect_status: bool, project_assigner) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        with self._benchmark.measure('process_specs', spec_count=len(specs)):
            for spec in specs:
                result = self._process_spec(
                    spec=spec,
                    existing=existing,
                    prev_hashes=prev_hashes,
                    dry_run=dry_run,
                    update=update,
                    respect_status=respect_status,
                    project_assigner=project_assigner,
                )
                results.append({'spec': spec, 'result': result})
        return results

    def _sync_build_summary(self, specs: List[IssueSpec], processed: List[Dict[str, Any]]) -> Dict[str, Any]:
        created: List[Dict[str, Any]] = []
        updated: List[Dict[str, Any]] = []
        closed: List[Dict[str, Any]] = []
        mapping: Dict[str, int] = {}
        skipped = 0
        for entry in processed:
            spec: IssueSpec = entry['spec']
            result: Dict[str, Any] = entry['result']
            if result.get('created'):
                created.append({'external_id': spec.external_id, 'title': spec.title, 'hash': spec.hash})
            if mapped := result.get('mapped'):
                mapping[spec.external_id] = mapped
            if closed_entry := result.get('closed'):
                closed.append(closed_entry)
            if updated_entry := result.get('updated'):
                updated.append(updated_entry)
            if result.get('skipped'):
                skipped += 1
        return {
            'totals': {
                'specs': len(specs),
                'created': len(created),
                'updated': len(updated),
                'closed': len(closed),
                'skipped': skipped
            },
            'changes': {'created': created, 'updated': updated, 'closed': closed},
            'mapping': mapping,
        }

    def _process_spec(self, *, spec: IssueSpec, existing: List[Dict[str, Any]], prev_hashes: Dict[str, str],
                      dry_run: bool, update: bool, respect_status: bool, project_assigner) -> Dict[str, Any]:
        """Process a single spec returning a result map with one of keys:
        created | updated | closed | skipped plus optional mapped (issue number).
        Keeps logic isolated to lower cognitive complexity of sync().
        """
        result: Dict[str, Any] = {}
        match = self._match(spec, existing)
        prev_hash = prev_hashes.get(spec.external_id)
        if not match:
            self._create(spec, dry_run)
            result['created'] = True
            return result
        number = match.get('number') if isinstance(match, dict) else None
        if isinstance(number, int):
            result['mapped'] = number
            try:  # project assignment (noop currently)
                project_assigner.assign(number, spec)
            except Exception:  # pragma: no cover - defensive
                pass
        if respect_status and spec.status == 'closed' and match.get('state') != 'CLOSED':
            self._close(match, dry_run)
            result['closed'] = {'external_id': spec.external_id, 'number': match['number']}
            return result
        if update and self._needs_update(spec, match, prev_hash):
            diff = self._diff(spec, match)
            self._update(spec, match, dry_run)
            result['updated'] = {'external_id': spec.external_id, 'number': match['number'], 'diff': diff}
            return result
        result['skipped'] = True
        return result

    # --- internal helpers ---
    def _gh_auth(self) -> bool:
        if self._mock:
            return False
        try:
            subprocess.check_output(['gh','auth','status'], stderr=subprocess.STDOUT)
            return True
        except Exception:
            return False

    def _existing_issues(self) -> list[dict[str, Any]]:
        try:
            out = subprocess.check_output(['gh','issue','list','--state','all','--limit','1000','--json','number,title,body,labels,milestone,state'], text=True)
            return json.loads(out)
        except Exception:
            return []

    def _match(self, spec: IssueSpec, existing: list[dict[str, Any]]) -> dict[str, Any] | None:
        import re
        norm = lambda t: re.sub(r'\s+',' ', t.lower())
        for issue in existing:
            if issue['title'] == spec.title:
                return issue
            if spec.external_id in issue['title'] and norm(issue['title']) == norm(spec.title):
                return issue
        return None

    def _needs_update(self, spec: IssueSpec, issue: dict[str, Any], prev_hash: Optional[str]) -> bool:
        if prev_hash and prev_hash == spec.hash:
            return False
        existing_labels = {l['name'] for l in (issue.get('labels') or [])}
        if set(spec.labels) != existing_labels:
            return True
        desired_ms = spec.milestone or ''
        existing_ms = (issue.get('milestone') or {}).get('title','')
        if desired_ms and desired_ms != existing_ms:
            return True
        body = (issue.get('body') or '').strip()
        return body != spec.body.strip()

    def _diff(self, spec: IssueSpec, issue: dict[str, Any]) -> dict[str, Any]:
        import difflib
        d: Dict[str, Any] = {}
        existing_labels = {l['name'] for l in (issue.get('labels') or [])}
        if set(spec.labels) != existing_labels:
            d['labels_added'] = sorted(set(spec.labels) - existing_labels)
            d['labels_removed'] = sorted(existing_labels - set(spec.labels))
        desired_ms = spec.milestone or ''
        existing_ms = (issue.get('milestone') or {}).get('title','')
        if desired_ms and desired_ms != existing_ms:
            d['milestone_from'] = existing_ms
            d['milestone_to'] = desired_ms
        old_body = (issue.get('body') or '').strip().splitlines()
        new_body = spec.body.strip().splitlines()
        if old_body != new_body:
            diff_lines = list(difflib.unified_diff(old_body, new_body, lineterm='', n=3))
            if len(diff_lines) > 120:
                diff_lines = diff_lines[:120] + ['... (truncated)']
            d['body_changed'] = True
            d['body_diff'] = diff_lines
        return d

    def _create(self, spec: IssueSpec, dry_run: bool) -> None:
        self._log('create', spec.external_id, 'dry_run' if dry_run else '')
        self._logger.log_issue_action('create', spec.external_id, dry_run=dry_run)
        
        if self._mock:
            print('MOCK create:', spec.external_id)
            return
        cmd = ['gh','issue','create','--title', spec.title,'--body', spec.body]
        if spec.labels:
            cmd += ['--label', ','.join(spec.labels)]
        if spec.milestone:
            cmd += ['--milestone', spec.milestone]
        if dry_run:
            print('DRY-RUN create:', ' '.join(cmd))
            return
        subprocess.check_call(cmd)

    def _update(self, spec: IssueSpec, issue: dict[str, Any], dry_run: bool) -> None:
        number = str(issue['number'])
        self._log('update', spec.external_id, f'#{number}', 'dry_run' if dry_run else '')
        self._logger.log_issue_action('update', spec.external_id, int(number), dry_run=dry_run)
        
        if self._mock:
            print('MOCK update:', spec.external_id, f'#{number}')
            return
        if dry_run:
            print(f'DRY-RUN update: #{number}')
            return
        if spec.labels:
            subprocess.check_call(['gh','issue','edit', number, '--add-label', ','.join(spec.labels)])
        if spec.milestone:
            subprocess.check_call(['gh','issue','edit', number, '--milestone', spec.milestone])
        subprocess.check_call(['gh','api', f'repos/:owner/:repo/issues/{number}', '--method','PATCH','-f', f'body={spec.body}'])

    def _close(self, issue: dict[str, Any], dry_run: bool) -> None:
        number = str(issue['number'])
        self._log('close', f'#{number}', 'dry_run' if dry_run else '')
        self._logger.log_issue_action('close', issue.get('title', 'unknown'), int(number), dry_run=dry_run)
        
        if self._mock:
            print('MOCK close:', number)
            return
        if dry_run:
            print(f'DRY-RUN close: {number}')
            return
        subprocess.check_call(['gh','issue','close', number])

    def _hash_state_path(self) -> Path:
        return self.cfg.source_file.parent / self.cfg.hash_state_file

    def _load_hash_state(self) -> Dict[str, str]:
        p = self._hash_state_path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                return data.get('hashes', {})
            except Exception:
                return {}
        return {}

    def _save_hash_state(self, specs: list[IssueSpec]) -> None:
        p = self._hash_state_path()
        p.write_text(json.dumps({'hashes': {s.external_id: s.hash for s in specs}}, indent=2) + '\n')

    # --- preflight helpers (label & milestone ensure) ---
    def _preflight(self, specs: list[IssueSpec]) -> None:  # orchestrator entry
        if not (self.cfg.ensure_labels_enabled or self.cfg.ensure_milestones_enabled):
            return
        if self.cfg.ensure_labels_enabled:
            self._ensure_labels(specs)
        if self.cfg.ensure_milestones_enabled and self.cfg.ensure_milestones_list:
            self._ensure_milestones()

    def _ensure_labels(self, specs: list[IssueSpec]) -> None:  # pragma: no cover - network side-effects
        if self._mock:
            return
        import subprocess
        desired = sorted({l for s in specs for l in s.labels} | set(self.cfg.inject_labels))
        try:
            out = subprocess.check_output(['gh','label','list','--limit','300','--json','name','--jq','.[].name'], text=True)
            existing = set(out.strip().splitlines())
        except Exception:
            existing = set()
        for lbl in desired:
            if lbl in existing:
                continue
            try:
                subprocess.check_call([
                    'gh','label','create', lbl,
                    '--color','ededed',
                    '--description','Auto-created (issuesuite)'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _ensure_milestones(self) -> None:  # pragma: no cover - network side-effects
        if self._mock:
            return
        import subprocess
        try:
            out = subprocess.check_output(['gh','api','repos/:owner/:repo/milestones','--paginate','--jq','.[].title'], text=True)
            existing = set(out.strip().splitlines())
        except Exception:
            existing = set()
        for ms in self.cfg.ensure_milestones_list:
            if ms in existing:
                continue
            try:
                subprocess.check_call([
                    'gh','api','repos/:owner/:repo/milestones',
                    '-f', f'title={ms}',
                    '-f','description=Auto-created (issuesuite)'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    
    # Concurrency support methods
    async def _get_existing_issues_async(self) -> List[Dict[str, Any]]:
        """Get existing issues asynchronously."""
        if self._mock:
            return []
        
        with create_async_github_client(self._concurrency_config, self._mock) as client:
            success, issues = await client.get_issues_async()
            return issues if success else []
    
    def _process_spec_wrapper(self, spec: IssueSpec, existing: List[Dict[str, Any]], 
                            prev_hashes: Dict[str, str], dry_run: bool, update: bool, 
                            respect_status: bool, project_assigner) -> Dict[str, Any]:
        """Wrapper for _process_spec to be used with concurrent processing."""
        return self._process_spec(
            spec=spec,
            existing=existing,
            prev_hashes=prev_hashes,
            dry_run=dry_run,
            update=update,
            respect_status=respect_status,
            project_assigner=project_assigner
        )
    
    async def sync_async(self, *, dry_run: bool, update: bool, respect_status: bool, preflight: bool) -> Dict[str, Any]:
        """Async sync method with concurrency support for large roadmaps."""
        with self._logger.timed_operation('sync_async', dry_run=dry_run, update=update, 
                                         respect_status=respect_status, preflight=preflight):
            self._log('sync_async:start', f'dry_run={dry_run}')
            specs = self.parse()
            self._logger.log_operation('parse_complete', spec_count=len(specs))
            
            # Auto-adjust concurrency based on roadmap size
            if self.cfg.concurrency_enabled and len(specs) >= 10:
                optimal_workers = get_optimal_worker_count(len(specs), self.cfg.concurrency_max_workers)
                self._concurrency_config.max_workers = optimal_workers
                self._logger.log_operation('concurrency_adjusted', 
                                         spec_count=len(specs), 
                                         workers=optimal_workers)
            
            if preflight:
                self._preflight(specs)
            
            project_assigner = build_project_assigner(ProjectConfig(
                enabled=bool(getattr(self.cfg, 'project_enable', False)),
                number=getattr(self.cfg, 'project_number', None),
                field_mappings=getattr(self.cfg, 'project_field_mappings', {}) or {},
            ))
            
            # Get existing issues asynchronously if concurrency is enabled
            if self.cfg.concurrency_enabled:
                existing = await self._get_existing_issues_async() if self._gh_auth() else []
            else:
                existing = self._existing_issues() if self._gh_auth() else []
            
            self._logger.log_operation('fetch_existing_issues', issue_count=len(existing))
            prev_hashes = self._load_hash_state()
            
            # Process specs concurrently
            if self.cfg.concurrency_enabled and len(specs) > 1:
                processor = create_concurrent_processor(self._concurrency_config, self._mock)
                results = await processor.process_specs_concurrent(
                    specs, self._process_spec_wrapper,
                    existing, prev_hashes, dry_run, update, respect_status, project_assigner
                )
            else:
                # Sequential fallback
                results = []
                for spec in specs:
                    result = self._process_spec(
                        spec=spec, existing=existing, prev_hashes=prev_hashes,
                        dry_run=dry_run, update=update, respect_status=respect_status,
                        project_assigner=project_assigner
                    )
                    results.append(result)
            
            # Aggregate results
            created = []
            updated = []
            closed = []
            mapping = {}
            skipped = 0
            
            for i, result in enumerate(results):
                if isinstance(result, dict) and 'error' not in result:
                    spec = specs[i]
                    if result.get('created'):
                        created.append({'external_id': spec.external_id, 'title': spec.title, 'hash': spec.hash})
                    if mapped := result.get('mapped'):
                        mapping[spec.external_id] = mapped
                    if closed_entry := result.get('closed'):
                        closed.append(closed_entry)
                    if updated_entry := result.get('updated'):
                        updated.append(updated_entry)
                    if result.get('skipped'):
                        skipped += 1
                else:
                    skipped += 1
            
            if not dry_run:
                self._save_hash_state(specs)
            
            summary = {
                'totals': {
                    'specs': len(specs),
                    'created': len(created),
                    'updated': len(updated),
                    'closed': len(closed),
                    'skipped': skipped
                },
                'changes': {'created': created, 'updated': updated, 'closed': closed},
                'mapping': mapping,
            }
            
            self._logger.log_operation('sync_async_complete', **{
                'issues_created': summary['totals']['created'],
                'issues_updated': summary['totals']['updated'],
                'issues_closed': summary['totals']['closed'],
                'specs': summary['totals']['specs'],
                'skipped': summary['totals']['skipped']
            })
            return summary
