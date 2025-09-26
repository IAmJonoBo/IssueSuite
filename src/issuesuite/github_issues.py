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
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

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

    def __init__(self, cfg: IssuesClientConfig):
        self.cfg = cfg
        self._env_quiet = os.environ.get("ISSUESUITE_QUIET") == "1"

    # --- internal helpers -------------------------------------------------
    def _base_cmd(self, *parts: str) -> list[str]:
        cmd: list[str] = ["gh", *parts]
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
                lambda: subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
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
        self._run(self._base_cmd("issue", "close", str(number)))

    def list_existing(self) -> list[dict[str, Any]]:
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
            if 'not a git repository' in str(exc).lower():
                print('[list_existing] non-git directory; returning empty list')
                return []
            raise
        if not out.strip():
            return []
        try:
            data = json.loads(out)
            if isinstance(data, list):
                return cast(list[dict[str, Any]], data)
            return []
        except Exception:  # pragma: no cover - defensive
            return []


__all__ = [
    "IssuesClientConfig",
    "IssuesClient",
]
