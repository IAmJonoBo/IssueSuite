from __future__ import annotations

import contextlib
import requests
import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from issuesuite.dependency_audit import Advisory
from issuesuite.pip_audit_integration import (
    ResilientPyPIService,
    collect_online_findings,
    install_resilient_pip_audit,
)

try:
    from pip_audit._cli import VulnerabilityServiceChoice  # type: ignore[attr-defined]
    from pip_audit._service.interface import ResolvedDependency  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    VulnerabilityServiceChoice = None  # type: ignore[assignment]
    ResolvedDependency = None  # type: ignore[assignment]


ADVISORY = Advisory(
    package="requests",
    specifiers=SpecifierSet("<2.32.0"),
    vulnerability_id="GHSA-j8r2-6x86-q33q",
    description="Requests header parsing issue",
    severity="medium",
    fixed_versions=("2.32.0",),
    reference=None,
)


def _build_service() -> ResilientPyPIService:
    return ResilientPyPIService(cache_dir=None, timeout=None, advisories=[ADVISORY])


def test_resilient_service_falls_back_to_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    if ResolvedDependency is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")
    service = _build_service()

    def _raise(*args, **kwargs):
        raise requests.exceptions.SSLError("boom")

    monkeypatch.setattr(service.session, "get", _raise)
    spec = ResolvedDependency(name="requests", version=Version("2.31.0"))
    dependency, results = service.query(spec)

    assert dependency is spec
    assert [result.id for result in results] == ["GHSA-j8r2-6x86-q33q"]
    assert service.fallback_events


def test_resilient_service_merges_offline_results(monkeypatch: pytest.MonkeyPatch) -> None:
    if ResolvedDependency is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")
    service = _build_service()

    class _Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"vulnerabilities": None}

    monkeypatch.setattr(service.session, "get", lambda *args, **kwargs: _Response())
    spec = ResolvedDependency(name="requests", version=Version("2.31.0"))
    dependency, results = service.query(spec)

    assert dependency is spec
    assert len(results) == 1
    assert results[0].id == "GHSA-j8r2-6x86-q33q"
    assert not service.fallback_events


def test_resilient_service_records_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    if ResolvedDependency is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")

    recorded: list[tuple[str, str]] = []

    class _Span:
        def set_attribute(self, key: str, value: str) -> None:
            recorded.append((key, value))

    class _Tracer:
        def start_as_current_span(self, name: str):
            recorded.append(("span", name))

            @contextlib.contextmanager
            def _manager():
                yield _Span()

            return _manager()

    monkeypatch.setattr("issuesuite.pip_audit_integration._get_tracer", lambda *_: _Tracer())

    service = _build_service()

    def _raise(*args, **kwargs):
        raise requests.exceptions.SSLError("boom")

    monkeypatch.setattr(service.session, "get", _raise)
    spec = ResolvedDependency(name="requests", version=Version("2.31.0"))
    service.query(spec)

    assert ("span", "issuesuite.pip_audit.fallback") in recorded
    assert ("issuesuite.package", "requests") in recorded


def test_install_resilient_pip_audit_overrides_choice() -> None:
    if ResolvedDependency is None or VulnerabilityServiceChoice is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")
    restore = install_resilient_pip_audit()
    try:
        service = VulnerabilityServiceChoice.Pypi.to_service(timeout=5, cache_dir=None)
        assert isinstance(service, ResilientPyPIService)
    finally:
        restore()


def test_collect_online_findings_returns_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    if ResolvedDependency is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")

    restore = install_resilient_pip_audit(advisories=[ADVISORY])
    try:
        findings = collect_online_findings()
    finally:
        restore()

    assert isinstance(findings, list)
