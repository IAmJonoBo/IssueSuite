from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

import pytest


def _load_sitecustomize() -> ModuleType:
    module_name = "sitecustomize"
    module_path = pathlib.Path(__file__).resolve().parents[1] / "sitecustomize.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Unable to load sitecustomize module specification")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_sitecustomize_disable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ISSUESUITE_DISABLE_PIP_AUDIT_SITE_PATCH", "1")
    module = _load_sitecustomize()

    assert module._patch_pip_audit() is False


def test_sitecustomize_installs_resilient_service(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_sitecustomize()
    monkeypatch.setattr(module, "_load_advisories", lambda: ("advisory",))
    called: dict[str, tuple[object, ...]] = {}

    def _fake_install(advisories: object) -> object:
        called["advisories"] = tuple(advisories)
        return lambda: None

    monkeypatch.setattr(module, "_install_resilient_service", _fake_install)
    monkeypatch.delenv("ISSUESUITE_DISABLE_PIP_AUDIT_SITE_PATCH", raising=False)

    assert module._patch_pip_audit() is True
    assert called["advisories"] == ("advisory",)
