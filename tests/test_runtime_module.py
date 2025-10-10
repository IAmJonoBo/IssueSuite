from __future__ import annotations

from types import SimpleNamespace

import pytest

from issuesuite import runtime


class StubConfig:
    def __init__(self) -> None:
        self.github_repo: str | None = None
        self.project_number: int | None = None
        self.project_enable: bool = False


def test_prepare_config_returns_none_for_init_command() -> None:
    args = SimpleNamespace(cmd="init")
    assert runtime.prepare_config(args) is None


def test_prepare_config_requires_config_attribute() -> None:
    args = SimpleNamespace(cmd="sync")
    with pytest.raises(AttributeError):
        runtime.prepare_config(args)


def test_prepare_config_applies_repo_and_project_number() -> None:
    args = SimpleNamespace(
        cmd="sync", config="config.yml", repo="owner/repo", project_number="12"
    )

    def loader(path: str) -> StubConfig:
        assert path == "config.yml"
        return StubConfig()

    cfg = runtime.prepare_config(args, loader=loader)
    assert cfg is not None
    assert cfg.github_repo == "owner/repo"
    assert cfg.project_number == 12
    assert cfg.project_enable is True


def test_execute_command_success(monkeypatch: pytest.MonkeyPatch) -> None:
    args = SimpleNamespace(foo="bar", _plugin_payload={"trace": "ok"})
    cfg = StubConfig()
    plugin_calls: list[tuple[str, dict[str, object]]] = []
    telemetry_calls: list[tuple[str, int, float]] = []

    def fake_invoke(
        config: StubConfig | None, command: str, payload: dict[str, object]
    ) -> None:
        plugin_calls.append((command, payload))

    def fake_emit(
        config: StubConfig | None, command: str, exit_code: int, duration: float
    ) -> None:
        telemetry_calls.append((command, exit_code, duration))

    monkeypatch.setattr(runtime.plugins, "invoke_plugins", fake_invoke)
    monkeypatch.setattr(runtime.telemetry, "emit", fake_emit)

    exit_code = runtime.execute_command(lambda: 5, args, cfg, "sync")

    assert exit_code == 5
    assert plugin_calls and plugin_calls[0][0] == "sync"
    assert plugin_calls[0][1]["trace"] == "ok"
    assert telemetry_calls and telemetry_calls[0][1] == 5


def test_execute_command_propagates_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    args = SimpleNamespace(foo="bar", _plugin_payload={})
    cfg = StubConfig()
    plugin_calls: list[int] = []

    def fake_invoke(
        config: StubConfig | None, command: str, payload: dict[str, object]
    ) -> None:
        plugin_calls.append(payload["exit_code"])  # type: ignore[index]

    def fake_emit(
        config: StubConfig | None, command: str, exit_code: int, duration: float
    ) -> None:
        plugin_calls.append(exit_code)

    monkeypatch.setattr(runtime.plugins, "invoke_plugins", fake_invoke)
    monkeypatch.setattr(runtime.telemetry, "emit", fake_emit)

    def boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        runtime.execute_command(boom, args, cfg, "sync")

    assert plugin_calls[0] == 1
