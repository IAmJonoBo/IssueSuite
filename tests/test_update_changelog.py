from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import IO, Any

import pytest


def _load_module() -> ModuleType:
    path = Path("scripts/update_changelog.py")
    spec = importlib.util.spec_from_file_location("update_changelog", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


_module = _load_module()


def _acquire_lock(handle: IO[Any]) -> None:
    return _module._acquire_lock(handle)


def update_changelog(path: Path, *, version: str, highlights: list[str]) -> str:
    return _module.update_changelog(path, version=version, highlights=highlights)


def test_update_changelog_inserts_entry(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## 0.1.10 - 2024-01-01\n\n- Previous entry\n")

    entry = update_changelog(
        changelog,
        version="0.1.11",
        highlights=["Added offline dependency audit fallback"],
    )

    assert "0.1.11" in entry
    contents = changelog.read_text()
    non_empty = [line for line in contents.splitlines() if line]
    assert non_empty[1].startswith("## 0.1.11")


def test_acquire_lock_raises_when_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyHandle:
        def fileno(self) -> int:  # pragma: no cover - trivial helper
            return 0

    def fake_flock(fd: int, flags: int) -> None:
        raise BlockingIOError

    monkeypatch.setattr("fcntl.flock", fake_flock)

    with pytest.raises(RuntimeError):
        _acquire_lock(DummyHandle())


def test_update_changelog_preserves_file_on_lock_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    original = "# Changelog\n\n## 0.1.10 - 2024-01-01\n\n- Previous entry\n"
    changelog.write_text(original)

    def fail_lock(
        handle: IO[Any],
    ) -> None:  # pragma: no cover - behaviour asserted via exception
        raise RuntimeError("locked")

    monkeypatch.setattr(_module, "_acquire_lock", fail_lock)

    with pytest.raises(RuntimeError):
        update_changelog(
            changelog,
            version="0.1.12",
            highlights=["Guard against data loss when changelog is locked"],
        )

    assert changelog.read_text() == original
