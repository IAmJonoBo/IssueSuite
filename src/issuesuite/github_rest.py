from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from .retry import run_with_retries

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_GRAPHQL_URL = "https://api.github.com/graphql"
USER_AGENT = "issuesuite-rest/0.1.11"
HTTP_ERROR_STATUS = 400


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub REST/GraphQL API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.response_text = response_text


@dataclass
class GitHubRestClient:
    """Lightweight REST/GraphQL client for GitHub operations."""

    token: str
    repo: str
    base_url: str = DEFAULT_API_URL
    graphql_url: str = DEFAULT_GRAPHQL_URL
    session: requests.Session | None = None
    _session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:  # pragma: no cover - simple wiring
        self._session = self.session or requests.Session()
        self._session.headers.setdefault("Authorization", f"Bearer {self.token}")
        self._session.headers.setdefault("Accept", "application/vnd.github+json")
        self._session.headers.setdefault("User-Agent", USER_AGENT)

    # ---- REST helpers -------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        url = (
            path
            if path.startswith("http")
            else f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        )

        def _run() -> requests.Response:
            return self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=self._session.headers,
                timeout=30,
            )

        response = run_with_retries(_run)
        if response.status_code >= HTTP_ERROR_STATUS:
            raise GitHubAPIError(
                f"GitHub API {method} {url} failed with {response.status_code}",
                status=response.status_code,
                response_text=response.text,
            )
        if response.text:
            try:
                return response.json()
            except Exception:  # pragma: no cover - defensive
                return response.text
        return None

    def _paginate(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> list[Any]:
        params = dict(params or {})
        per_page = params.setdefault("per_page", 100)
        params.setdefault("page", 1)
        results: list[Any] = []
        while True:
            data = self._request("GET", path, params=params)
            if not isinstance(data, list):
                break
            results.extend(data)
            if len(data) < per_page:
                break
            params["page"] = params.get("page", 1) + 1
        return results

    # ---- Issue operations --------------------------------------------
    def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: Iterable[str] | None = None,
        milestone: str | None = None,
    ) -> int | None:
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = list(labels)
        if milestone:
            resolved = self._resolve_milestone(milestone)
            if resolved is not None:
                payload["milestone"] = resolved
        data = self._request("POST", f"/repos/{self.repo}/issues", json_body=payload)
        if isinstance(data, dict):
            number = data.get("number")
            if isinstance(number, int):
                return number
        return None

    def update_issue(
        self,
        *,
        number: int,
        body: str | None = None,
        labels: Iterable[str] | None = None,
        milestone: str | None = None,
        state: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {}
        if body is not None:
            payload["body"] = body
        if labels is not None:
            payload["labels"] = list(labels)
        if milestone is not None:
            resolved = self._resolve_milestone(milestone)
            if resolved is not None:
                payload["milestone"] = resolved
        if state is not None:
            payload["state"] = state
        if payload:
            self._request(
                "PATCH", f"/repos/{self.repo}/issues/{number}", json_body=payload
            )

    def close_issue(self, *, number: int) -> None:
        self.update_issue(number=number, state="closed")

    def list_issues(self, *, state: str = "open") -> list[dict[str, Any]]:
        params = {"state": state, "per_page": 100, "page": 1}
        data = self._paginate(f"/repos/{self.repo}/issues", params=params)
        out: list[dict[str, Any]] = []
        for entry in data:
            if isinstance(entry, dict):
                out.append(entry)
        return out

    # ---- GraphQL ------------------------------------------------------
    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        payload = {"query": query, "variables": variables or {}}
        data = self._request("POST", self.graphql_url, json_body=payload)
        if isinstance(data, dict) and "errors" in data:
            raise GitHubAPIError(f"GraphQL query failed: {data['errors']}")
        return data

    # ---- Utilities ----------------------------------------------------
    def _resolve_milestone(self, milestone: str) -> int | None:
        milestone = milestone.strip()
        if milestone.isdigit():
            return int(milestone)
        milestones = self._paginate(
            f"/repos/{self.repo}/milestones", params={"state": "all"}
        )
        for entry in milestones:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title")
            if isinstance(title, str) and title.lower() == milestone.lower():
                number = entry.get("number")
                if isinstance(number, int):
                    return number
        return None


def compute_signature(entries: dict[str, Any]) -> str:
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


@dataclass
class GitHubIndex:
    entries: dict[str, dict[str, Any]]
    repo: str | None = None
    version: int = 1
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    signature: str = ""

    def with_signature(self) -> GitHubIndex:
        self.signature = compute_signature(self.entries)
        return self


def serialize_index(document: GitHubIndex) -> dict[str, Any]:
    doc = {
        "version": document.version,
        "generated_at": document.generated_at,
        "repo": document.repo,
        "entries": document.entries,
        "signature": document.signature or compute_signature(document.entries),
    }
    return doc


def deserialize_index(raw: dict[str, Any]) -> GitHubIndex:
    entries = raw.get("entries")
    repo = raw.get("repo") if isinstance(raw.get("repo"), str) else None
    if not isinstance(entries, dict):
        entries = {}
    doc = GitHubIndex(entries=entries, repo=repo)
    doc.version = int(raw.get("version") or 1)
    doc.generated_at = str(raw.get("generated_at") or doc.generated_at)
    doc.signature = str(raw.get("signature") or "")
    return doc


__all__ = [
    "GitHubAPIError",
    "GitHubRestClient",
    "GitHubIndex",
    "serialize_index",
    "deserialize_index",
]
