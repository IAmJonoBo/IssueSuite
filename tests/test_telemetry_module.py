from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from issuesuite import telemetry


@pytest.fixture(autouse=True)
def reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ISSUESUITE_TELEMETRY", raising=False)
    monkeypatch.delenv("ISSUESUITE_TELEMETRY_PATH", raising=False)


def test_resolve_config_honours_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ISSUESUITE_TELEMETRY", "1")
    monkeypatch.setenv("ISSUESUITE_TELEMETRY_PATH", "custom.log")
    cfg = SimpleNamespace(
        telemetry_enabled=False, telemetry_store_path=str(tmp_path / "ignored.log")
    )

    resolved = telemetry.resolve_config(cfg)

    assert resolved.enabled is True
    assert resolved.store_path.name == "custom.log"


def test_emit_writes_line_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "telemetry.jsonl"
    cfg = SimpleNamespace(telemetry_enabled=True, telemetry_store_path=str(target))

    class FakeTime:
        def strftime(self, fmt: str, ts: object) -> str:
            return "2025-01-01T00:00:00Z"

        def gmtime(self) -> object:
            return object()

    monkeypatch.setattr(telemetry, "time", FakeTime())
    telemetry.emit(cfg, "sync", 0, 0.25)

    payload = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert payload["command"] == "sync"
    assert payload["duration_ms"] == 250


def test_emit_skips_when_disabled(tmp_path: Path) -> None:
    cfg = SimpleNamespace(
        telemetry_enabled=False, telemetry_store_path=str(tmp_path / "telemetry.jsonl")
    )
    telemetry.emit(cfg, "sync", 1, 0.5)
    assert not (tmp_path / "telemetry.jsonl").exists()
