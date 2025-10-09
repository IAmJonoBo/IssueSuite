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


def test_sitecustomize_load_advisories_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _load_advisories when dependency_audit module is available."""
    module = _load_sitecustomize()
    
    # Mock the advisory data
    mock_advisories = [{"id": "GHSA-1234", "package": "test"}]
    
    # Mock the dependency_audit module
    class MockDependencyAudit:
        @staticmethod
        def load_advisories():
            return mock_advisories
    
    monkeypatch.setattr(module, "import_module", lambda name: MockDependencyAudit() if name == "issuesuite.dependency_audit" else None)
    
    result = module._load_advisories()
    assert tuple(result) == tuple(mock_advisories)


def test_sitecustomize_load_advisories_missing_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _load_advisories when dependency_audit module is missing."""
    module = _load_sitecustomize()
    
    def mock_import_module(name: str):
        if name == "issuesuite.dependency_audit":
            raise ImportError("Module not found")
        return None
    
    monkeypatch.setattr(module, "import_module", mock_import_module)
    
    result = module._load_advisories()
    assert tuple(result) == ()


def test_sitecustomize_install_resilient_service_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _install_resilient_service when pip_audit_integration is available."""
    module = _load_sitecustomize()
    
    restore_called = False
    
    def mock_install_resilient_pip_audit(advisories):
        def restore():
            nonlocal restore_called
            restore_called = True
        return restore
    
    class MockIntegration:
        install_resilient_pip_audit = staticmethod(mock_install_resilient_pip_audit)
    
    monkeypatch.setattr(module, "import_module", lambda name: MockIntegration() if name == "issuesuite.pip_audit_integration" else None)
    
    result = module._install_resilient_service([{"id": "test"}])
    assert result is True


def test_sitecustomize_install_resilient_service_missing_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _install_resilient_service when pip_audit_integration is missing."""
    module = _load_sitecustomize()
    
    def mock_import_module(name: str):
        if name == "issuesuite.pip_audit_integration":
            raise ImportError("Module not found")
        return None
    
    monkeypatch.setattr(module, "import_module", mock_import_module)
    
    result = module._install_resilient_service([])
    assert result is False


def test_sitecustomize_install_resilient_service_missing_installer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _install_resilient_service when install_resilient_pip_audit attribute is missing."""
    module = _load_sitecustomize()
    
    class MockIntegration:
        pass  # Missing install_resilient_pip_audit attribute
    
    monkeypatch.setattr(module, "import_module", lambda name: MockIntegration() if name == "issuesuite.pip_audit_integration" else None)
    
    result = module._install_resilient_service([])
    assert result is False


def test_sitecustomize_patch_pip_audit_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test end-to-end _patch_pip_audit integration."""
    module = _load_sitecustomize()
    
    advisories_loaded = []
    restore_called = False
    
    def mock_load_advisories():
        advisories_loaded.append("loaded")
        return [{"id": "GHSA-test"}]
    
    def mock_install_resilient_service(advisories):
        nonlocal restore_called
        def restore():
            nonlocal restore_called
            restore_called = True
        return restore() if advisories else False
    
    monkeypatch.setattr(module, "_load_advisories", mock_load_advisories)
    monkeypatch.setattr(module, "_install_resilient_service", mock_install_resilient_service)
    monkeypatch.delenv("ISSUESUITE_DISABLE_PIP_AUDIT_SITE_PATCH", raising=False)
    
    result = module._patch_pip_audit()
    assert result is False  # Because mock_install_resilient_service returns restore() which is None
    assert len(advisories_loaded) == 1

