import json
from dataclasses import dataclass
from typing import Any

import pytest

from issuesuite.github_issues import IssuesClient, IssuesClientConfig
from issuesuite.github_rest import GitHubAPIError, GitHubRestClient


@dataclass
class _DummyResponse:
    status_code: int
    payload: Any

    def json(self) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    @property
    def text(self) -> str:
        payload = self.payload
        if isinstance(payload, dict):
            return json.dumps(payload)
        if isinstance(payload, list):
            return json.dumps(payload)
        return str(payload)


class _DummySession:
    def __init__(self, responses: list[_DummyResponse]):
        self._responses = responses
        self.request_log: list[tuple[str, str, dict[str, Any]]] = []
        self.headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> _DummyResponse:
        self.request_log.append((method, url, {"headers": headers, "json": json, "params": params}))
        if not self._responses:
            raise AssertionError("No response queued for request")
        return self._responses.pop(0)


def test_rest_client_creates_issue_with_milestone_resolution():
    session = _DummySession(
        [
            _DummyResponse(200, [{"title": "Sprint 1", "number": 7}]),
            _DummyResponse(201, {"number": 321}),
        ]
    )
    client = GitHubRestClient(token="tkn", repo="acme/widgets", session=session)

    number = client.create_issue(title="Demo", body="Body", labels=["bug"], milestone="Sprint 1")

    assert number == 321
    assert session.request_log[0][0] == "GET"
    assert session.request_log[0][1].endswith("/repos/acme/widgets/milestones")
    assert session.request_log[1][0] == "POST"
    assert session.request_log[1][1].endswith("/repos/acme/widgets/issues")
    assert session.request_log[1][2]["json"]["milestone"] == 7


def test_rest_client_raises_on_error():
    session = _DummySession([
        _DummyResponse(500, {"message": "boom"}),
    ])
    client = GitHubRestClient(token="tkn", repo="acme/widgets", session=session)

    with pytest.raises(GitHubAPIError):
        client.list_issues(state="all")


class _RecordingRestClient(GitHubRestClient):
    def __init__(self):
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_issue(self, **kwargs: Any) -> int | None:  # type: ignore[override]
        self.calls.append(("create", kwargs))
        return 99

    def update_issue(self, **kwargs: Any) -> None:  # type: ignore[override]
        self.calls.append(("update", kwargs))

    def close_issue(self, **kwargs: Any) -> None:  # type: ignore[override]
        self.calls.append(("close", kwargs))

    def list_issues(self, **kwargs: Any) -> list[dict[str, Any]]:  # type: ignore[override]
        self.calls.append(("list", kwargs))
        return [{"number": 1, "title": "demo"}]


def test_issues_client_prefers_rest_when_available(monkeypatch):
    cfg = IssuesClientConfig(repo="acme/widgets", dry_run=False, mock=False)
    rest = _RecordingRestClient()
    client = IssuesClient(cfg, rest_client=rest)

    assert client.create_issue(title="Demo", body="Body") == 99
    assert rest.calls and rest.calls[0][0] == "create"
    client.update_issue(number=42, body="Body2")
    client.close_issue(number=42)
    assert [c[0] for c in rest.calls] == ["create", "update", "close"]


def test_issues_client_falls_back_to_cli_when_rest_disabled(monkeypatch):
    cfg = IssuesClientConfig(repo="acme/widgets", dry_run=True, mock=False)
    monkeypatch.setenv("ISSUESUITE_REST_DISABLED", "1")
    client = IssuesClient(cfg, rest_client=None)
    recorded: list[list[str]] = []
    monkeypatch.setattr(client, "_run", lambda cmd: recorded.append(cmd) or "")

    client.create_issue(title="X", body="Y")
    assert recorded, "CLI fallback should record commands"
