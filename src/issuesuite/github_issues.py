"""GitHub Issues CRUD abstraction.

Encapsulates all direct GitHub CLI (``gh``) interactions for creating,
updating and closing issues so that core sync logic can be simplified
and future backends (REST API / GraphQL / App installation) can plug in.

Design goals:
 - Single place for command construction & parsing
 - Support dry-run (emit planned command but do not execute)
 - Support mock mode (print MOCK action, never shell out)
 - Attempt to capture created issue number deterministically
 - Small surface area: create / update / close / list_existing
 - Repository scoping via ``-R owner/repo`` when repo provided

NOTE: The current implementation shells out to the GitHub CLI exactly
like the legacy inline code. When more reliable structured responses are
required we can switch to ``gh api`` calls (or direct HTTP) that return
JSON. For now we parse the stdout of ``gh issue create`` to extract the
issue number when possible (pattern: ``/issues/<number>``).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404 - subprocess is required for GitHub CLI invocation
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .github_rest import (
    DEFAULT_API_URL,
    DEFAULT_GRAPHQL_URL,
    GitHubAPIError,
    GitHubRestClient,
)
from .retry import run_with_retries

NUMBER_PATTERN = re.compile(r"/issues/(\d+)")


@dataclass
class IssuesClientConfig:
    repo: str | None = None  # owner/repo; if None gh defaults to current directory remote
    mock: bool = False
    dry_run: bool = False


class IssuesClient:
    """Thin wrapper around GitHub issue operations.

    Public methods raise RuntimeError on command failures to simplify
    caller error handling (core code can catch & log). In mock mode we
    return fabricated / empty data structures and never raise.
    """

    # Class-level mock counter for deterministic fabricated issue numbers in mock mode
    _mock_counter: int = 1000

    def __init__(self, cfg: IssuesClientConfig, rest_client: GitHubRestClient | None = None):
        self.cfg = cfg
        self._env_quiet = os.environ.get("ISSUESUITE_QUIET") == "1"
        self._gh_path = shutil.which("gh")
        self._rest_client: GitHubRestClient | None
        if rest_client is not None:
            self._rest_client = rest_client
        else:
            self._rest_client = self._build_rest_client()

    # --- internal helpers -------------------------------------------------
    def _base_cmd(self, *parts: str) -> list[str]:
        gh_base = self._gh_path if self._gh_path else "gh"
        cmd: list[str] = [gh_base, *parts]
        if self.cfg.repo:
            cmd.extend(["-R", self.cfg.repo])
        return cmd

    def _run(self, cmd: list[str]) -> str:
        if self.cfg.mock:
            print("MOCK", " ".join(cmd))
            return ""
        if self.cfg.dry_run:
            print("DRY-RUN", " ".join(cmd))
            return ""
        try:
            return run_with_retries(
                lambda: subprocess.check_output(  # nosec B603 B607 - command uses controlled arguments
                    cmd, text=True, stderr=subprocess.STDOUT
                )
            )
        except (
            subprocess.CalledProcessError
        ) as exc:  # pragma: no cover - propagate consistent RuntimeError
            raise RuntimeError(f"Command failed: {' '.join(cmd)}: {exc.output}") from exc

    # --- CRUD operations --------------------------------------------------
    def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: Iterable[str] | None = None,
        milestone: str | None = None,
    ) -> int | None:
        rest_client = self._get_rest_client()
        if rest_client is not None:
            if self.cfg.dry_run:
                print("DRY-RUN REST POST /issues", title)
                return None
            try:
                return rest_client.create_issue(
                    title=title,
                    body=body,
                    labels=labels,
                    milestone=milestone,
                )
            except GitHubAPIError as exc:  # pragma: no cover - network failures
                if not self._env_quiet:
                    print(f"[rest] create_issue fallback to gh: {exc}")
            # fall back to CLI path

        cmd = self._base_cmd("issue", "create", "--title", title, "--body", body)
        label_list = list(labels or [])
        if label_list:
            cmd.extend(["--label", ",".join(label_list)])
        if milestone:
            cmd.extend(["--milestone", milestone])
        out = self._run(cmd)
        # In mock mode (non dry-run) fabricate deterministic incremental number so mapping persists
        if self.cfg.mock and not self.cfg.dry_run:
            IssuesClient._mock_counter += 1
            return int(IssuesClient._mock_counter)  # noqa: PLW2901
        # Attempt to parse created number from output
        match = NUMBER_PATTERN.search(out)
        if match:
            try:
                return int(match.group(1))
            except ValueError:  # pragma: no cover - defensive
                return None
        return None

    def update_issue(
        self,
        *,
        number: int,
        body: str | None = None,
        labels: Iterable[str] | None = None,
        milestone: str | None = None,
    ) -> None:
        rest_client = self._get_rest_client()
        if rest_client is not None:
            if self.cfg.dry_run:
                print(f"DRY-RUN REST PATCH /issues/{number}")
                return
            try:
                rest_client.update_issue(
                    number=number,
                    body=body,
                    labels=labels,
                    milestone=milestone,
                )
                return
            except GitHubAPIError as exc:  # pragma: no cover
                if not self._env_quiet:
                    print(f"[rest] update_issue fallback to gh: {exc}")

        # GitHub CLI edit semantics: adding labels with --add-label merges; we may
        # want full reconciliation later (remove extraneous) via --remove-label.
        label_list = list(labels or [])
        if label_list:
            self._run(
                self._base_cmd("issue", "edit", str(number), "--add-label", ",".join(label_list))
            )
        if milestone:
            self._run(self._base_cmd("issue", "edit", str(number), "--milestone", milestone))
        if body is not None:
            # Use gh api for body patch (consistent with existing code)
            self._run(
                self._base_cmd(
                    "api",
                    f"repos/:owner/:repo/issues/{number}",
                    "--method",
                    "PATCH",
                    "-f",
                    f"body={body}",
                )
            )

    def close_issue(self, *, number: int) -> None:
        rest_client = self._get_rest_client()
        if rest_client is not None:
            if self.cfg.dry_run:
                print(f"DRY-RUN REST PATCH /issues/{number} state=closed")
                return
            try:
                rest_client.close_issue(number=number)
                return
            except GitHubAPIError as exc:  # pragma: no cover
                if not self._env_quiet:
                    print(f"[rest] close_issue fallback to gh: {exc}")
        self._run(self._base_cmd("issue", "close", str(number)))

    def list_existing(self) -> list[dict[str, Any]]:
        rest_client = self._get_rest_client()
        if rest_client is not None:
            try:
                data = rest_client.list_issues(state="all")
            except GitHubAPIError as exc:  # pragma: no cover
                if not self._env_quiet:
                    print(f"[rest] list_issues fallback to gh: {exc}")
            else:
                return [self._normalize_issue(entry) for entry in data]
        return self._list_existing_via_cli()

    def _list_existing_via_cli(self) -> list[dict[str, Any]]:
        cmd = self._base_cmd(
            "issue",
            "list",
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title,body,labels,milestone,state",
        )
        if self.cfg.mock:
            return []
        if self.cfg.dry_run:
            # Still fetch to enable diff planning even in dry-run (no mutation) unless
            # that becomes too chatty; for now we actually run it.
            pass
        try:
            out = self._run(cmd)
        except RuntimeError as exc:  # pragma: no cover - environment dependent
            # In some ephemeral temp directories (tests) gh may fail if not a git repo
            if "not a git repository" in str(exc).lower():
                print("[list_existing] non-git directory; returning empty list")
                return []
            raise
        if not out.strip():
            return []
        return self._parse_issue_list(out)

    @staticmethod
    def _parse_issue_list(payload: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(payload)
        except Exception:  # pragma: no cover - defensive
            return []
        if not isinstance(data, list):
            return []
        filtered: list[dict[str, Any]] = []
        for entry in data:
            if isinstance(entry, dict):
                filtered.append(entry)
        return filtered

    # --- REST helpers --------------------------------------------------
    def _get_rest_client(self) -> GitHubRestClient | None:
        if self.cfg.mock:
            return None
        return self._rest_client

    def _build_rest_client(self) -> GitHubRestClient | None:
        if self.cfg.mock:
            return None
        if self._env_flag("ISSUESUITE_REST_DISABLED"):
            return None
        token = self._select_token()
        repo = (self.cfg.repo or "").strip()
        if not token or not repo:
            return None
        base_url = self._clean_env("ISSUESUITE_GITHUB_API", DEFAULT_API_URL)
        graphql_url = self._clean_env("ISSUESUITE_GITHUB_GRAPHQL", DEFAULT_GRAPHQL_URL)
        return GitHubRestClient(token=token, repo=repo, base_url=base_url, graphql_url=graphql_url)

    @staticmethod
    def _select_token() -> str | None:
        for name in ("ISSUESUITE_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            raw = os.environ.get(name)
            if raw is None:
                continue
            token = raw.strip()
            if token:
                return token
        return None

    @staticmethod
    def _env_flag(name: str) -> bool:
        value = os.environ.get(name)
        if value is None:
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _clean_env(name: str, default: str) -> str:
        value = os.environ.get(name)
        if value is None:
            return default
        cleaned = value.strip()
        return cleaned or default

    @staticmethod
    def _normalize_issue(entry: dict[str, Any]) -> dict[str, Any]:
        labels: list[str] = []
        raw_labels = entry.get("labels")
        if isinstance(raw_labels, list):
            for lbl in raw_labels:
                if isinstance(lbl, dict):
                    name = lbl.get("name")
                    if isinstance(name, str):
                        labels.append(name)
                elif isinstance(lbl, str):
                    labels.append(lbl)
        milestone = entry.get("milestone")
        milestone_title: str | None = None
        if isinstance(milestone, dict):
            mt = milestone.get("title")
            if isinstance(mt, str):
                milestone_title = mt
        elif isinstance(milestone, str):
            milestone_title = milestone
        return {
            "number": entry.get("number"),
            "title": entry.get("title"),
            "body": entry.get("body", ""),
            "labels": labels,
            "milestone": milestone_title,
            "state": entry.get("state"),
        }


__all__ = [
    "IssuesClientConfig",
    "IssuesClient",
]
