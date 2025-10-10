from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import shutil
import subprocess  # nosec B404 - subprocess is required for GitHub CLI integration
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from .benchmarking import BenchmarkConfig, create_benchmark
from .concurrency import (
    ConcurrencyConfig,
    create_async_github_client,
    create_concurrent_processor,
    get_optimal_worker_count,
)
from .config import SuiteConfig
from .diffing import compute_diff, needs_update
from .env_auth import EnvAuthConfig, create_env_auth_manager
from .github_auth import GitHubAppConfig, create_github_app_manager
from .github_issues import IssuesClient, IssuesClientConfig
from .logging import configure_logging
from .models import IssueSpec
from .parser import ParseError, parse_issues
from .project import ProjectConfig, build_project_assigner

# Hidden marker template for idempotent issue recognition
_MARKER_PREFIX = "<!-- issuesuite:slug="


def _ensure_marker(body: str, slug: str) -> str:
    """Ensure the hidden slug marker is present at top of body.

    We always place marker as first line to simplify matching and avoid duplication.
    """
    marker = f"{_MARKER_PREFIX}{slug} -->"
    if marker in body:
        return body
    if body.startswith("#") or body.startswith("<!--"):
        # Still prepend marker with blank line after for readability
        return marker + "\n\n" + body
    return marker + "\n\n" + body


class PlanEntry(TypedDict, total=False):
    external_id: str
    title: str
    action: str  # create|update|close|skip
    number: int | None
    labels: list[str]
    milestone: str | None
    reason: str | None
    changes: dict[str, int] | None


def _plan_match_issue(
    spec: IssueSpec, existing: list[dict[str, Any]]
) -> dict[str, Any] | None:
    for issue in existing:
        title = issue.get("title")
        if title == spec.title:
            return issue
        if spec.external_id in (title or "") and re.sub(
            r"\s+", " ", (title or "").lower()
        ) == re.sub(r"\s+", " ", spec.title.lower()):
            return issue
    return None


def _plan_changes(spec: IssueSpec, issue: dict[str, Any]) -> dict[str, int]:
    diff = compute_diff(spec, issue)
    return {
        "labels_added": len(diff.get("labels_added", [])),
        "labels_removed": len(diff.get("labels_removed", [])),
        "body_changed": 1 if diff.get("body_changed") else 0,
        "milestone_changed": 1 if diff.get("milestone_changed") else 0,
    }


def _plan_entry_for_spec(
    spec: IssueSpec,
    existing: list[dict[str, Any]],
    prev_hashes: dict[str, str],
    update: bool,
    respect_status: bool,
) -> PlanEntry:
    issue = _plan_match_issue(spec, existing)
    prev_hash = prev_hashes.get(spec.external_id)
    if not issue:
        return PlanEntry(
            external_id=spec.external_id,
            title=spec.title,
            action="create",
            number=None,
            labels=spec.labels,
            milestone=spec.milestone,
            reason="no existing match",
            changes=None,
        )
    number = issue.get("number") if isinstance(issue.get("number"), int) else None
    if respect_status and spec.status == "closed" and issue.get("state") != "CLOSED":
        return PlanEntry(
            external_id=spec.external_id,
            title=spec.title,
            action="close",
            number=number,
            labels=spec.labels,
            milestone=spec.milestone,
            reason=None,
            changes=None,
        )
    if update and needs_update(spec, issue, prev_hash):
        return PlanEntry(
            external_id=spec.external_id,
            title=spec.title,
            action="update",
            number=number,
            labels=spec.labels,
            milestone=spec.milestone,
            reason=None,
            changes=_plan_changes(spec, issue),
        )
    return PlanEntry(
        external_id=spec.external_id,
        title=spec.title,
        action="skip",
        number=number,
        labels=spec.labels,
        milestone=spec.milestone,
        reason=None,
        changes=None,
    )


def _build_plan(
    specs: list[IssueSpec],
    existing: list[dict[str, Any]],
    prev_hashes: dict[str, str],
    update: bool,
    respect_status: bool,
) -> list[PlanEntry]:
    return [
        _plan_entry_for_spec(spec, existing, prev_hashes, update, respect_status)
        for spec in specs
    ]


# Canonical label normalization map (mirrors legacy script)
_LABEL_CANON_MAP = {
    "p0-critical": "P0-critical",
    "p1-important": "P1-important",
    "p2-enhancement": "P2-enhancement",
}

# Concurrency threshold for switching to worker pool
_concurrency_threshold_default = 10


class ProjectAssignerProtocol(Protocol):  # narrow contract used in core for typing
    def assign(
        self, issue_number: int, spec: Any
    ) -> None: ...  # pragma: no cover - structural only


class BenchmarkProtocol(Protocol):  # minimal protocol to appease type checker
    def measure(
        self, operation: str, **context: Any
    ) -> AbstractContextManager[None]: ...  # pragma: no cover
    def generate_report(self) -> None: ...  # pragma: no cover


class _ConcurrentProcessorProtocol(
    Protocol
):  # narrow structural type for concurrency helper
    async def process_specs_concurrent(  # pragma: no cover - runtime provided
        self,
        specs: list[IssueSpec],
        processor_func: Any,
        *args: Any,
    ) -> list[dict[str, Any]]: ...


_yaml: Any
try:  # YAML is mandatory for new parser; if missing we raise at runtime when parse called
    _yaml = cast(Any, importlib.import_module("yaml"))
except Exception:  # pragma: no cover
    _yaml = cast(Any, None)

# IssueSpec now sourced from models.py


class IssueSuite:
    # forward attribute type annotations for static analyzers
    _env_auth_manager: Any | None
    _github_app_manager: Any | None
    _benchmark: BenchmarkProtocol

    def __init__(self, cfg: SuiteConfig):
        self.cfg = cfg
        self._debug = os.environ.get("ISSUESUITE_DEBUG") == "1"
        # Mock mode: skip all GitHub CLI invocations even in non-dry-run paths
        self._mock = os.environ.get("ISSUES_SUITE_MOCK") == "1"
        # Last error classification (populated on failure for orchestrator embedding)
        self._last_error: dict[str, Any] | None = None

        # Configure structured logging based on config
        self._logger = configure_logging(
            json_logging=cfg.logging_json_enabled, level=cfg.logging_level
        )

        # Configure environment authentication
        if cfg.env_auth_enabled:
            self._env_auth_manager = create_env_auth_manager(
                EnvAuthConfig(
                    load_dotenv=cfg.env_auth_load_dotenv,
                    dotenv_path=cfg.env_auth_dotenv_path,
                )
            )
            # Setup authentication from environment
            self._setup_env_authentication()
        else:
            self._env_auth_manager = None

        # Configure concurrency
        self._concurrency_config = ConcurrencyConfig(
            enabled=cfg.concurrency_enabled,
            max_workers=cfg.concurrency_max_workers,
            batch_size=10,  # Default batch size
        )

        # Configure GitHub App authentication
        self._github_app_config = GitHubAppConfig(
            enabled=cfg.github_app_enabled,
            app_id=cfg.github_app_id,
            private_key_path=cfg.github_app_private_key_path,
            installation_id=cfg.github_app_installation_id,
        )
        self._github_app_manager = None

        # Configure performance benchmarking
        self._benchmark_config = BenchmarkConfig(
            enabled=cfg.performance_benchmarking,
            output_file="performance_report.json",
            collect_system_metrics=True,
            track_memory=True,
            track_cpu=True,
        )
        self._benchmark: BenchmarkProtocol = create_benchmark(self._benchmark_config, self._mock)  # type: ignore[assignment]

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
                self._logger.log_operation(
                    "env_auth_configured", source="environment_variables"
                )

            # Log authentication recommendations if needed
            recommendations = (
                self._env_auth_manager.get_authentication_recommendations()
            )
            # Suppress recommendation noise when quiet mode requested
            if recommendations and os.environ.get("ISSUESUITE_QUIET") != "1":
                self._logger.info(
                    "Authentication recommendations: " + "; ".join(recommendations)
                )

            # Detect online environment
            if self._env_auth_manager.is_online_environment():
                self._logger.log_operation("online_environment_detected")

        except Exception as e:
            self._logger.log_error(
                "Environment authentication setup failed", error=str(e)
            )

    def _setup_github_app_auth(self) -> None:
        """Setup GitHub App authentication."""
        try:
            self._github_app_manager = create_github_app_manager(
                self._github_app_config, self._mock
            )

            if self._github_app_manager.is_enabled():
                success = self._github_app_manager.configure_github_cli()
                if success:
                    self._logger.log_operation(
                        "github_app_auth_configured",
                        app_id=self._github_app_config.app_id,
                    )
                else:
                    self._logger.log_error(
                        "Failed to configure GitHub App authentication"
                    )
        except Exception as e:
            self._logger.log_error(
                "GitHub App authentication setup failed", error=str(e)
            )

    def _log(self, *parts: Any) -> None:  # lightweight internal debug logger
        if self._debug:
            print("[issuesuite]", *parts)
        # Also log via structured logger
        self._logger.debug(" ".join(str(p) for p in parts))

    @classmethod
    def from_config_path(cls, path: str | Path) -> IssueSuite:
        from .config import (  # local import to avoid circular  # noqa: PLC0415
            load_config,
        )

        return cls(load_config(path))

    def parse(self) -> list[IssueSpec]:  # thin wrapper over parser module
        path = self.cfg.source_file
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        try:
            specs = parse_issues(lines)
        except ParseError as exc:
            raise ValueError(str(exc)) from exc
        return specs

    def sync(
        self,
        *,
        dry_run: bool,
        update: bool,
        respect_status: bool,
        preflight: bool,
        prune: bool = False,
    ) -> dict[str, Any]:
        from .errors import (  # noqa: PLC0415 - local import to avoid cycles and only on demand
            classify_error,
        )

        try:
            with (
                self._benchmark.measure(
                    "sync_total",
                    dry_run=dry_run,
                    update=update,
                    respect_status=respect_status,
                    preflight=preflight,
                ),
                self._logger.timed_operation(
                    "sync",
                    dry_run=dry_run,
                    update=update,
                    respect_status=respect_status,
                    preflight=preflight,
                ),
            ):
                self._log(
                    "sync:start",
                    f"dry_run={dry_run}",
                    f"update={update}",
                    f"respect_status={respect_status}",
                    f"preflight={preflight}",
                )

                specs = self._sync_parse_and_preflight(preflight)
                project_assigner = self._build_project_assigner()
                existing = self._sync_fetch_existing(preflight)
                prev_hashes = self._load_hash_state()
                plan: list[PlanEntry] | None = None
                if dry_run:
                    plan = _build_plan(
                        specs, existing, prev_hashes, update, respect_status
                    )
                results = self._sync_process_specs(
                    specs,
                    existing,
                    prev_hashes,
                    dry_run,
                    update,
                    respect_status,
                    project_assigner,
                )
                if prune and not dry_run:
                    self._prune_unmatched(existing, results, dry_run)
                summary = self._sync_build_summary(specs, results)
                if plan is not None:
                    summary["plan"] = plan

                if not dry_run:
                    with self._benchmark.measure("save_hash_state"):
                        self._save_hash_state(specs)

                self._log("sync:done", summary["totals"])
                self._logger.log_operation(
                    "sync_complete",
                    issues_created=summary["totals"]["created"],
                    issues_updated=summary["totals"]["updated"],
                    issues_closed=summary["totals"]["closed"],
                    specs=summary["totals"]["specs"],
                    skipped=summary["totals"]["skipped"],
                )

                if self._benchmark_config.enabled:
                    self._benchmark.generate_report()
                return summary
        except Exception as exc:  # broad catch to enrich logging then re-raise
            info = classify_error(exc)
            # Log structured error classification for observability
            self._logger.log_error(
                "sync_failed",
                category=info.category,
                transient=info.transient,
                original_type=info.original_type,
                error=info.message,
            )
            # Store for orchestrator embedding (best-effort)
            self._last_error = {
                "category": info.category,
                "transient": info.transient,
                "original_type": info.original_type,
                "message": info.message,
            }
            raise

    # --- sync refactor helpers ---
    def _sync_parse_and_preflight(self, preflight: bool) -> list[IssueSpec]:
        with self._benchmark.measure("parse_specs", spec_count="pending"):
            specs = self.parse()
        self._log("sync:parsed", len(specs), "specs")
        self._logger.log_operation("parse_complete", spec_count=len(specs))
        # Milestone enforcement: when configured, ensure every spec has a milestone
        if self.cfg.milestone_required:
            missing = [s.external_id for s in specs if not s.milestone]
            if missing:
                preview_limit = 5  # limit number of ids shown in exception
                self._logger.log_error(
                    "milestone_required_missing", count=len(missing), ids=missing[:10]
                )
                preview = ", ".join(missing[:preview_limit])
                suffix = "..." if len(missing) > preview_limit else ""
                raise ValueError(
                    f"Milestone required but missing for {len(missing)} spec(s): {preview}{suffix}"
                )
        if preflight:
            with self._benchmark.measure("preflight_setup"):
                self._preflight(specs)
        return specs

    def _build_project_assigner(self) -> ProjectAssignerProtocol:
        assigner = build_project_assigner(
            ProjectConfig(
                enabled=bool(getattr(self.cfg, "project_enable", False)),
                number=getattr(self.cfg, "project_number", None),
                field_mappings=getattr(self.cfg, "project_field_mappings", {}) or {},
            )
        )
        return assigner  # conforms to ProjectAssignerProtocol

    # --- Issues client factory -------------------------------------------------
    def _build_issues_client(self, *, dry_run: bool) -> IssuesClient:
        return IssuesClient(
            IssuesClientConfig(
                repo=self.cfg.github_repo,
                mock=self._mock,
                dry_run=dry_run,
            )
        )

    def _sync_fetch_existing(self, preflight: bool) -> list[dict[str, Any]]:
        with self._benchmark.measure("fetch_existing_issues"):
            if preflight and not (
                self.cfg.ensure_labels_enabled or self.cfg.ensure_milestones_enabled
            ):
                existing: list[dict[str, Any]] = []
            else:
                existing = self._existing_issues() if self._gh_auth() else []
        self._log("sync:existing_issues", len(existing))
        self._logger.log_operation("fetch_existing_issues", issue_count=len(existing))
        return existing

    def _sync_process_specs(
        self,
        specs: list[IssueSpec],
        existing: list[dict[str, Any]],
        prev_hashes: dict[str, str],
        dry_run: bool,
        update: bool,
        respect_status: bool,
        project_assigner: ProjectAssignerProtocol,
    ) -> list[dict[str, Any]]:
        # Sequential fast path (default) unless concurrency explicitly enabled in config.
        if (
            not self._concurrency_config.enabled
            or len(specs) < _concurrency_threshold_default
        ):
            results: list[dict[str, Any]] = []
            with self._benchmark.measure(
                "process_specs", spec_count=len(specs), mode="sequential"
            ):
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
                    results.append({"spec": spec, "result": result})
            return results

        # Concurrency path: leverage concurrent processor to parallelize _process_spec.
        async def _run() -> list[dict[str, Any]]:
            processor = create_concurrent_processor(
                self._concurrency_config, mock=self._mock
            )

            def _wrapper(spec: IssueSpec) -> dict[str, Any]:  # executed in threads
                return self._process_spec(
                    spec=spec,
                    existing=existing,
                    prev_hashes=prev_hashes,
                    dry_run=dry_run,
                    update=update,
                    respect_status=respect_status,
                    project_assigner=project_assigner,
                )

            processed = await processor.process_specs_concurrent(specs, _wrapper)
            return [
                {"spec": spec, "result": result}
                for spec, result in zip(specs, processed, strict=False)
            ]

        with self._benchmark.measure(
            "process_specs", spec_count=len(specs), mode="concurrent"
        ):
            try:
                # If already in an event loop (e.g., when called from async tests),
                # fall back to explicit sequential processing to avoid recursion.
                loop = asyncio.get_event_loop()
                if loop.is_running():  # pragma: no cover - defensive
                    seq_sequential: list[dict[str, Any]] = []
                    with self._benchmark.measure(
                        "process_specs", spec_count=len(specs), mode="sequential"
                    ):
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
                            seq_sequential.append({"spec": spec, "result": result})
                    return seq_sequential
                return asyncio.run(_run())
            except Exception:  # pragma: no cover - defensive fallback
                seq_fallback: list[dict[str, Any]] = []
                with self._benchmark.measure(
                    "process_specs", spec_count=len(specs), mode="sequential"
                ):
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
                        seq_fallback.append({"spec": spec, "result": result})
                return seq_fallback

    def _sync_build_summary(
        self, specs: list[IssueSpec], processed: list[dict[str, Any]]
    ) -> dict[str, Any]:
        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        closed: list[dict[str, Any]] = []
        mapping: dict[str, int] = {}
        skipped = 0
        for entry in processed:
            spec: IssueSpec = entry["spec"]
            result: dict[str, Any] = entry["result"]
            if result.get("created"):
                created.append(
                    {
                        "external_id": spec.external_id,
                        "title": spec.title,
                        "hash": spec.hash,
                    }
                )
            if mapped := result.get("mapped"):
                mapping[spec.external_id] = mapped
            if closed_entry := result.get("closed"):
                closed.append(closed_entry)
            if updated_entry := result.get("updated"):
                updated.append(updated_entry)
            if result.get("skipped"):
                skipped += 1
        return {
            "totals": {
                "specs": len(specs),
                "created": len(created),
                "updated": len(updated),
                "closed": len(closed),
                "skipped": skipped,
            },
            "changes": {"created": created, "updated": updated, "closed": closed},
            "mapping": mapping,
        }

    def _process_spec(
        self,
        *,
        spec: IssueSpec,
        existing: list[dict[str, Any]],
        prev_hashes: dict[str, str],
        dry_run: bool,
        update: bool,
        respect_status: bool,
        project_assigner: ProjectAssignerProtocol,
    ) -> dict[str, Any]:
        """Process a single spec returning a result map with one of keys:
        created | updated | closed | skipped plus optional mapped (issue number).
        Keeps logic isolated to lower cognitive complexity of sync().
        """
        result: dict[str, Any] = {}
        match = self._match(spec, existing)
        prev_hash = prev_hashes.get(spec.external_id)
        if not match:
            created_number = self._create(spec, dry_run)
            result["created"] = True
            if isinstance(created_number, int):
                result["mapped"] = created_number
            # Attempt project assignment (mock + non-dry-run only; real issue number unknown until GH returns it)
            self._maybe_assign_project_on_create(
                spec, project_assigner, result, dry_run
            )
            return result
        number = match.get("number") if match else None
        if isinstance(number, int):
            result["mapped"] = number
            try:  # project assignment (noop currently)
                project_assigner.assign(number, spec)
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.log_error(
                    "Project assignment failed",
                    error=str(exc),
                    external_id=spec.external_id,
                )
        if (
            respect_status
            and spec.status == "closed"
            and match.get("state") != "CLOSED"
        ):
            self._close(match, dry_run)
            result["closed"] = {
                "external_id": spec.external_id,
                "number": match["number"],
            }
            return result
        if update and needs_update(spec, match, prev_hash):
            diff = compute_diff(spec, match)
            self._update(spec, match, dry_run)
            result["updated"] = {
                "external_id": spec.external_id,
                "number": match["number"],
                "diff": diff,
            }
            return result
        result["skipped"] = True
        return result

    # --- internal helpers ---
    def _gh_auth(self) -> bool:
        if self._mock:
            return False
        gh_path = shutil.which("gh")
        if not gh_path:
            self._logger.debug("GitHub CLI not available for auth status probe")
            return False
        try:
            subprocess.check_output(  # nosec B603 B607 - command uses resolved executable & constant args
                [gh_path, "auth", "status"], stderr=subprocess.STDOUT
            )
            return True
        except subprocess.CalledProcessError as exc:
            self._logger.log_error(
                "GitHub CLI auth status failed",
                error=exc.output or str(exc),
                executable=gh_path,
            )
        except OSError as exc:  # pragma: no cover - filesystem / permission edge
            self._logger.log_error(
                "GitHub CLI invocation error", error=str(exc), executable=gh_path
            )
        return False

    def _existing_issues(self) -> list[dict[str, Any]]:
        client = self._build_issues_client(dry_run=False)
        existing_raw = client.list_existing()
        # Explicit typing for static analysis
        existing: list[dict[str, Any]] = []
        for e in existing_raw:
            existing.append(e)
        return existing

    def _match(
        self, spec: IssueSpec, existing: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        def _norm(text: str) -> str:
            return re.sub(r"\s+", " ", text.lower())

        marker = f"{_MARKER_PREFIX}{spec.external_id} -->"
        for issue in existing:
            body = issue.get("body") or ""
            if isinstance(body, str) and marker in body:
                return issue
            title = issue.get("title")
            if title == spec.title:
                return issue
            if spec.external_id in (title or "") and _norm(title or "") == _norm(
                spec.title
            ):
                return issue
        return None

    # diff / update helpers now provided by diffing module

    def _create(self, spec: IssueSpec, dry_run: bool) -> int | None:
        self._log("create", spec.external_id, "dry_run" if dry_run else "")
        self._logger.log_issue_action("create", spec.external_id, dry_run=dry_run)
        client = self._build_issues_client(dry_run=dry_run)
        body_with_marker = _ensure_marker(spec.body, spec.external_id)
        return client.create_issue(
            title=spec.title,
            body=body_with_marker,
            labels=spec.labels,
            milestone=spec.milestone,
        )

    def _update(self, spec: IssueSpec, issue: dict[str, Any], dry_run: bool) -> None:
        number = int(issue["number"])
        self._log(
            "update", spec.external_id, f"#{number}", "dry_run" if dry_run else ""
        )
        self._logger.log_issue_action(
            "update", spec.external_id, number, dry_run=dry_run
        )
        client = self._build_issues_client(dry_run=dry_run)
        body_with_marker = _ensure_marker(spec.body, spec.external_id)
        client.update_issue(
            number=number,
            body=body_with_marker,
            labels=spec.labels,
            milestone=spec.milestone,
        )

    def _close(self, issue: dict[str, Any], dry_run: bool) -> None:
        number = int(issue["number"])
        self._log("close", f"#{number}", "dry_run" if dry_run else "")
        self._logger.log_issue_action(
            "close", issue.get("title", "unknown"), number, dry_run=dry_run
        )
        client = self._build_issues_client(dry_run=dry_run)
        client.close_issue(number=number)

    def _prune_unmatched(
        self,
        existing: list[dict[str, Any]],
        processed: list[dict[str, Any]],
        dry_run: bool,
    ) -> None:
        """Close any existing issues that did not match a spec (removed from ISSUES.md).

        Only operates when prune flag set and not dry-run.
        """
        matched_numbers: set[int] = set()
        for entry in processed:
            res = entry.get("result")
            if (
                isinstance(res, dict)
                and "mapped" in res
                and isinstance(res["mapped"], int)
            ):
                matched_numbers.add(res["mapped"])
        for issue in existing:
            num = issue.get("number")
            if isinstance(num, int) and num not in matched_numbers:
                try:
                    self._close(issue, dry_run)
                except Exception as exc:
                    self._logger.log_error(
                        "Failed to prune unmatched issue",
                        error=str(exc),
                        issue_number=num,
                    )

    def _hash_state_path(self) -> Path:
        return self.cfg.source_file.parent / self.cfg.hash_state_file

    def _maybe_assign_project_on_create(
        self,
        spec: IssueSpec,
        project_assigner: ProjectAssignerProtocol,
        result: dict[str, Any],
        dry_run: bool,
    ) -> None:
        """Best-effort project assignment immediately after creation.

        In mock mode we fabricate an issue number from the external id if numeric.
        Real mode would require capturing returned issue number from creation; left
        for future enhancement (will integrate once create path captures GH response).
        """
        if dry_run or not getattr(self.cfg, "project_enable", False):
            return
        if not self._mock:
            return  # defer until real post-create number capture implemented
        try:
            synthetic_number = int(spec.external_id)
        except ValueError:
            return
        if synthetic_number <= 0:
            return
        try:  # pragma: no cover - defensive around external project assigner
            project_assigner.assign(synthetic_number, spec)
            result["mapped"] = synthetic_number
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.log_error(
                "Project assignment failed in mock mode",
                error=str(exc),
                external_id=spec.external_id,
            )

    def _load_hash_state(self) -> dict[str, str]:
        p = self._hash_state_path()
        if not p.exists():
            return {}
        try:
            raw: Any = json.loads(p.read_text())
        except Exception:  # pragma: no cover
            return {}
        if not isinstance(raw, dict):
            return {}
        hashes = raw.get("hashes")
        if not isinstance(hashes, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in hashes.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out  # noqa: RUF100

    def _save_hash_state(self, specs: list[IssueSpec]) -> None:
        p = self._hash_state_path()
        p.write_text(
            json.dumps({"hashes": {s.external_id: s.hash for s in specs}}, indent=2)
            + "\n"
        )

    # --- preflight helpers (label & milestone ensure) ---
    def _preflight(self, specs: list[IssueSpec]) -> None:  # orchestrator entry
        if not (self.cfg.ensure_labels_enabled or self.cfg.ensure_milestones_enabled):
            return
        if self.cfg.ensure_labels_enabled:
            self._ensure_labels(specs)
        if self.cfg.ensure_milestones_enabled and self.cfg.ensure_milestones_list:
            self._ensure_milestones()

    def _ensure_labels(
        self, specs: list[IssueSpec]
    ) -> None:  # pragma: no cover - network side-effects
        if self._mock:
            return
        gh_path = shutil.which("gh")
        if not gh_path:
            self._logger.log_error("GitHub CLI unavailable for label ensure step")
            return
        desired = sorted(
            {label for spec in specs for label in spec.labels}
            | set(self.cfg.inject_labels)
        )
        try:
            out = subprocess.check_output(  # nosec B603 - command uses resolved gh path and static args
                [
                    gh_path,
                    "label",
                    "list",
                    "--limit",
                    "300",
                    "--json",
                    "name",
                    "--jq",
                    ".[].name",
                ],
                text=True,
            )
            existing: set[str] = set(out.strip().splitlines())
        except Exception as exc:
            self._logger.log_error(
                "Failed to list labels", error=str(exc), executable=gh_path
            )
            existing = set()
        for lbl in desired:
            if lbl in existing:
                continue
            try:
                subprocess.check_call(  # nosec B603 - command uses resolved gh path and static args
                    [
                        gh_path,
                        "label",
                        "create",
                        lbl,
                        "--color",
                        "ededed",
                        "--description",
                        "Auto-created (issuesuite)",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                self._logger.log_error(
                    "Failed to ensure label", error=str(exc), label=lbl
                )

    def _ensure_milestones(self) -> None:  # pragma: no cover - network side-effects
        if self._mock:
            return
        gh_path = shutil.which("gh")
        if not gh_path:
            self._logger.log_error("GitHub CLI unavailable for milestone ensure step")
            return
        try:
            out = subprocess.check_output(  # nosec B603 - command uses resolved gh path and static args
                [
                    gh_path,
                    "api",
                    "repos/:owner/:repo/milestones",
                    "--paginate",
                    "--jq",
                    ".[].title",
                ],
                text=True,
            )
            existing: set[str] = set(out.strip().splitlines())
        except Exception as exc:
            self._logger.log_error(
                "Failed to list milestones", error=str(exc), executable=gh_path
            )
            existing = set()
        for ms in self.cfg.ensure_milestones_list:
            if ms in existing:
                continue
            try:
                subprocess.check_call(  # nosec B603 - command uses resolved gh path and static args
                    [
                        gh_path,
                        "api",
                        "repos/:owner/:repo/milestones",
                        "-f",
                        f"title={ms}",
                        "-f",
                        "description=Auto-created (issuesuite)",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                self._logger.log_error(
                    "Failed to ensure milestone", error=str(exc), milestone=ms
                )

    # Concurrency support methods
    async def _get_existing_issues_async(self) -> list[dict[str, Any]]:
        """Get existing issues asynchronously."""
        if self._mock:
            return []

        with create_async_github_client(self._concurrency_config, self._mock) as client:
            success, issues = await client.get_issues_async()
            return issues if success else []

    def _process_spec_wrapper(
        self,
        spec: IssueSpec,
        existing: list[dict[str, Any]],
        prev_hashes: dict[str, str],
        dry_run: bool,
        update: bool,
        respect_status: bool,
        project_assigner: ProjectAssignerProtocol,
    ) -> dict[str, Any]:
        """Wrapper for _process_spec to be used with concurrent processing."""
        return self._process_spec(
            spec=spec,
            existing=existing,
            prev_hashes=prev_hashes,
            dry_run=dry_run,
            update=update,
            respect_status=respect_status,
            project_assigner=project_assigner,
        )

    async def sync_async(
        self, *, dry_run: bool, update: bool, respect_status: bool, preflight: bool
    ) -> dict[str, Any]:
        """Async sync method with concurrency support for large roadmaps.

        Refactored to reduce branching complexity by delegating to helpers.
        """
        with self._logger.timed_operation(
            "sync_async",
            dry_run=dry_run,
            update=update,
            respect_status=respect_status,
            preflight=preflight,
        ):
            self._log("sync_async:start", f"dry_run={dry_run}")
            specs = self.parse()
            self._logger.log_operation("parse_complete", spec_count=len(specs))
            self._adjust_concurrency_if_needed(len(specs))
            if preflight:
                self._preflight(specs)
            project_assigner = self._build_project_assigner()
            existing = await self._fetch_existing_async()
            self._logger.log_operation(
                "fetch_existing_issues", issue_count=len(existing)
            )
            prev_hashes = self._load_hash_state()
            results = await self._process_specs_async(
                specs,
                existing,
                prev_hashes,
                dry_run,
                update,
                respect_status,
                project_assigner,
            )
            summary = self._aggregate_results(specs, results, dry_run)
            self._logger.log_operation(
                "sync_async_complete",
                **{
                    "issues_created": summary["totals"]["created"],
                    "issues_updated": summary["totals"]["updated"],
                    "issues_closed": summary["totals"]["closed"],
                    "specs": summary["totals"]["specs"],
                    "skipped": summary["totals"]["skipped"],
                },
            )
            return summary

    def _adjust_concurrency_if_needed(self, spec_count: int) -> None:
        if (
            self.cfg.concurrency_enabled
            and spec_count >= _concurrency_threshold_default
        ):
            optimal_workers = get_optimal_worker_count(
                spec_count, self.cfg.concurrency_max_workers
            )
            self._concurrency_config.max_workers = optimal_workers
            self._logger.log_operation(
                "concurrency_adjusted", spec_count=spec_count, workers=optimal_workers
            )

    async def _fetch_existing_async(self) -> list[dict[str, Any]]:
        if not self._gh_auth():
            return []
        if self.cfg.concurrency_enabled:
            return await self._get_existing_issues_async()
        return self._existing_issues()

    async def _process_specs_async(
        self,
        specs: list[IssueSpec],
        existing: list[dict[str, Any]],
        prev_hashes: dict[str, str],
        dry_run: bool,
        update: bool,
        respect_status: bool,
        project_assigner: ProjectAssignerProtocol,
    ) -> list[dict[str, Any]]:
        if self.cfg.concurrency_enabled and len(specs) > 1:
            processor: _ConcurrentProcessorProtocol = create_concurrent_processor(
                self._concurrency_config, self._mock
            )
            concurrent_results: list[dict[str, Any]] = (
                await processor.process_specs_concurrent(
                    specs,
                    self._process_spec_wrapper,
                    existing,
                    prev_hashes,
                    dry_run,
                    update,
                    respect_status,
                    project_assigner,
                )
            )
            return concurrent_results
        # Sequential fallback
        results: list[dict[str, Any]] = []
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
            results.append(result)
        return results

    def _aggregate_results(
        self, specs: list[IssueSpec], results: list[dict[str, Any]], dry_run: bool
    ) -> dict[str, Any]:  # noqa: PLR0915
        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        closed: list[dict[str, Any]] = []
        mapping: dict[str, int] = {}
        skipped = 0
        for i, result in enumerate(results):
            if "error" in result:
                skipped += 1
                continue
            spec = specs[i]
            if result.get("created"):
                created.append(
                    {
                        "external_id": spec.external_id,
                        "title": spec.title,
                        "hash": spec.hash,
                    }
                )
            if mapped := result.get("mapped"):
                mapping[spec.external_id] = mapped
            if closed_entry := result.get("closed"):
                closed.append(closed_entry)
            if updated_entry := result.get("updated"):
                updated.append(updated_entry)
            if result.get("skipped"):
                skipped += 1
        if not dry_run:
            self._save_hash_state(specs)
        return {
            "totals": {
                "specs": len(specs),
                "created": len(created),
                "updated": len(updated),
                "closed": len(closed),
                "skipped": skipped,
            },
            "changes": {"created": created, "updated": updated, "closed": closed},
            "mapping": mapping,
        }
