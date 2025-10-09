from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Any, NoReturn

import pytest
import requests
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from issuesuite.dependency_audit import Advisory
from issuesuite.dependency_audit import Finding
from issuesuite.pip_audit_integration import (
    PipAuditError,
    ResilientPyPIService,
    collect_online_findings,
    install_resilient_pip_audit,
    run_resilient_pip_audit,
)

try:
    from pip_audit._cli import VulnerabilityServiceChoice  # type: ignore[attr-defined]
    from pip_audit._service.interface import (
        ResolvedDependency,  # type: ignore[attr-defined]
    )
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


def test_resilient_service_falls_back_to_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if ResolvedDependency is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")
    service = _build_service()

    def _raise(*args: object, **kwargs: object) -> NoReturn:
        raise requests.exceptions.SSLError("boom")

    monkeypatch.setattr(service.session, "get", _raise)
    spec = ResolvedDependency(name="requests", version=Version("2.31.0"))
    dependency, results = service.query(spec)

    assert dependency is spec
    assert [result.id for result in results] == ["GHSA-j8r2-6x86-q33q"]
    assert service.fallback_events


def test_resilient_service_merges_offline_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        def start_as_current_span(self, name: str) -> AbstractContextManager[_Span]:
            recorded.append(("span", name))

            @contextlib.contextmanager
            def _manager() -> Iterator[_Span]:
                yield _Span()

            return _manager()

    monkeypatch.setattr("issuesuite.pip_audit_integration._get_tracer", lambda *_: _Tracer())

    service = _build_service()

    def _raise(*args: object, **kwargs: object) -> NoReturn:
        raise requests.exceptions.SSLError("boom")

    monkeypatch.setattr(service.session, "get", _raise)
    spec = ResolvedDependency(name="requests", version=Version("2.31.0"))
    service.query(spec)

    assert ("span", "issuesuite.pip_audit.fallback") in recorded
    assert ("issuesuite.package", "requests") in recorded


def test_install_resilient_pip_audit_overrides_choice() -> None:
    if (
        ResolvedDependency is None or VulnerabilityServiceChoice is None
    ):  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")
    restore = install_resilient_pip_audit()
    try:
        service = VulnerabilityServiceChoice.Pypi.to_service(timeout=5, cache_dir=None)
        assert isinstance(service, ResilientPyPIService)
    finally:
        restore()


def test_collect_online_findings_returns_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if ResolvedDependency is None:  # pragma: no cover - pip-audit missing
        pytest.skip("pip-audit not installed")

    restore = install_resilient_pip_audit(advisories=[ADVISORY])
    try:
        payload = {
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.31.0",
                    "vulns": [
                        {
                            "id": "GHSA-j8r2-6x86-q33q",
                            "description": "Requests header parsing issue",
                            "fix_versions": ["2.32.0"],
                        }
                    ],
                }
            ]
        }

        completed = subprocess.CompletedProcess(
            args=["pip-audit", "--format", "json"],
            returncode=1,
            stdout=json.dumps(payload),
            stderr="",
        )

        monkeypatch.setattr(
            "issuesuite.pip_audit_integration._run_pip_audit",
            lambda *args, **kwargs: completed,
        )

        findings = list(collect_online_findings())
    finally:
        restore()

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert findings[0].package == "requests"
    assert findings[0].vulnerability_id == "GHSA-j8r2-6x86-q33q"


def test_collect_online_findings_respects_disable_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE", "1")
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration._run_pip_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    with pytest.raises(PipAuditError) as excinfo:
        list(collect_online_findings())

    assert "ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE" in str(excinfo.value)


def test_run_resilient_pip_audit_falls_back_on_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration._run_pip_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(PipAuditError("timeout")),
    )
    monkeypatch.setattr("issuesuite.pip_audit_integration.load_advisories", lambda: [])
    monkeypatch.setattr("issuesuite.pip_audit_integration.collect_installed_packages", lambda: [])

    def _mock_perform_audit(**kwargs: object) -> tuple[list[Finding], str]:
        assert kwargs["online_probe"] is False
        return ([], "offline-only")

    monkeypatch.setattr("issuesuite.pip_audit_integration.perform_audit", _mock_perform_audit)
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration.render_findings_table",
        lambda findings: "offline table",
    )

    rc = run_resilient_pip_audit(["--strict"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "offline table" in captured.out
    assert "pip-audit unavailable" in captured.err


def test_run_resilient_pip_audit_handles_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration._run_pip_audit",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode=2),
    )
    monkeypatch.setattr("issuesuite.pip_audit_integration.load_advisories", lambda: [])
    monkeypatch.setattr("issuesuite.pip_audit_integration.collect_installed_packages", lambda: [])

    def _mock_perform_audit(
        **kwargs: object,
    ) -> tuple[list[Finding], str | None]:
        return (
            [
                Finding(
                    package="requests",
                    installed_version="2.31.0",
                    vulnerability_id="GHSA-xxx",
                    description="Requests issue",
                    fixed_versions=("2.32.0",),
                    source="offline",
                )
            ],
            None,
        )

    monkeypatch.setattr("issuesuite.pip_audit_integration.perform_audit", _mock_perform_audit)
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration.render_findings_table",
        lambda findings: "offline finding",
    )

    rc = run_resilient_pip_audit(["--strict"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "offline finding" in captured.out
    assert "rc=2" in captured.err


def test_run_resilient_pip_audit_honours_disable_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE", "true")
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration._run_pip_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )
    monkeypatch.setattr("issuesuite.pip_audit_integration.load_advisories", lambda: [])
    monkeypatch.setattr("issuesuite.pip_audit_integration.collect_installed_packages", lambda: [])

    def _mock_perform_audit(**kwargs: object) -> tuple[list[Finding], str]:
        assert kwargs["online_probe"] is False
        return ([], "offline-only")

    monkeypatch.setattr("issuesuite.pip_audit_integration.perform_audit", _mock_perform_audit)
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration.render_findings_table",
        lambda findings: "offline table",
    )

    rc = run_resilient_pip_audit(["--strict"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "offline table" in captured.out
    assert "online-collection-disabled" in captured.err


def test_run_resilient_pip_audit_passthrough_outputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = subprocess.CompletedProcess(
        ("pip-audit",),
        returncode=0,
        stdout="audit summary",
        stderr="deprecation warning",
    )
    monkeypatch.setattr("issuesuite.pip_audit_integration._run_pip_audit", lambda *_, **__: result)

    rc = run_resilient_pip_audit(["--strict"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == "audit summary\n"
    assert captured.err == "deprecation warning\n"


def test_run_resilient_pip_audit_detects_ssl_in_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = subprocess.CompletedProcess(
        ("pip-audit",),
        returncode=1,
        stdout="HTTPSConnectionPool(host='example.com')",
        stderr="",
    )
    monkeypatch.setattr("issuesuite.pip_audit_integration._run_pip_audit", lambda *_, **__: result)
    monkeypatch.setattr("issuesuite.pip_audit_integration.load_advisories", lambda: [])
    monkeypatch.setattr("issuesuite.pip_audit_integration.collect_installed_packages", lambda: [])

    def _mock_perform_audit(**kwargs: object) -> tuple[list[Finding], str | None]:
        assert kwargs["online_probe"] is False
        return ([], "offline-only")

    monkeypatch.setattr("issuesuite.pip_audit_integration.perform_audit", _mock_perform_audit)
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration.render_findings_table",
        lambda findings: "offline table",
    )

    rc = run_resilient_pip_audit(["--strict"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "offline table" in captured.out
    assert "pip-audit unavailable (ssl-error)" in captured.err


def test_run_resilient_pip_audit_handles_missing_dependency(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = subprocess.CompletedProcess(
        ("pip-audit",),
        returncode=1,
        stdout="",
        stderr="Dependency not found on PyPI and could not be audited: issuesuite (0.1.13)",
    )
    monkeypatch.setattr("issuesuite.pip_audit_integration._run_pip_audit", lambda *_, **__: result)
    monkeypatch.setattr("issuesuite.pip_audit_integration.load_advisories", lambda: [])
    monkeypatch.setattr("issuesuite.pip_audit_integration.collect_installed_packages", lambda: [])

    def _mock_perform_audit(**kwargs: object) -> tuple[list[Finding], str | None]:
        assert kwargs["online_probe"] is False
        return ([], "offline-only")

    monkeypatch.setattr("issuesuite.pip_audit_integration.perform_audit", _mock_perform_audit)
    monkeypatch.setattr(
        "issuesuite.pip_audit_integration.render_findings_table",
        lambda findings: "offline table",
    )

    rc = run_resilient_pip_audit(["--strict"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "offline table" in captured.out
    assert "pip-audit unavailable (missing-dependency)" in captured.err
