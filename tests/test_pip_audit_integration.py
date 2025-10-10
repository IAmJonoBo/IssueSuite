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

from issuesuite.dependency_audit import Advisory, Finding
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


def test_get_audit_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _resolve_timeout with various environment values."""
    from issuesuite.pip_audit_integration import _resolve_timeout  # noqa: PLC0415

    # Test with no env var set
    monkeypatch.delenv("ISSUESUITE_PIP_AUDIT_TIMEOUT", raising=False)
    assert _resolve_timeout() == 60.0

    # Test with valid float
    monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_TIMEOUT", "120.5")
    assert _resolve_timeout() == 120.5

    # Test with invalid value (non-numeric)
    monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_TIMEOUT", "invalid")
    assert _resolve_timeout() == 60.0

    # Test with zero (should return None)
    monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_TIMEOUT", "0")
    assert _resolve_timeout() is None

    # Test with negative value (should return None)
    monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_TIMEOUT", "-10")
    assert _resolve_timeout() is None


def test_online_collection_disabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _online_collection_disabled with various environment values."""
    from issuesuite.pip_audit_integration import (  # noqa: PLC0415
        _online_collection_disabled,
    )

    # Test with no env var set
    monkeypatch.delenv("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE", raising=False)
    assert _online_collection_disabled() is False

    # Test with various truthy values
    for val in ["1", "true", "TRUE", "yes", "YES", "on", "ON"]:
        monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE", val)
        assert _online_collection_disabled() is True

    # Test with falsy values
    for val in ["0", "false", "no", "off", "other"]:
        monkeypatch.setenv("ISSUESUITE_PIP_AUDIT_DISABLE_ONLINE", val)
        assert _online_collection_disabled() is False


def test_parse_findings_with_invalid_payload() -> None:
    """Test _iter_entries and _extract_findings with invalid payload types."""
    from issuesuite.pip_audit_integration import (  # noqa: PLC0415
        _extract_findings,
        _iter_entries,
    )

    # Test with non-dict payload
    findings = list(_iter_entries("not a dict"))
    assert findings == []

    # Test with dict but non-list result field
    findings = list(_iter_entries({"results": "not a list"}))
    assert findings == []

    # Test with empty list
    findings = list(_iter_entries({"results": []}))
    assert findings == []

    # Test with non-dict entries in list
    findings = list(_iter_entries({"results": ["string", 123, None]}))
    assert findings == []

    # Test _extract_findings wrapper
    all_findings = list(_extract_findings({"results": []}))
    assert all_findings == []


def test_extract_alias_with_various_types() -> None:
    """Test _extract_alias with various alias types."""
    from issuesuite.pip_audit_integration import _extract_alias  # noqa: PLC0415

    # Test with list of aliases
    assert _extract_alias({"aliases": ["GHSA-1234", "CVE-2024-1234"]}) == "GHSA-1234"

    # Test with empty list
    assert _extract_alias({"aliases": []}) == ""

    # Test with tuple
    assert _extract_alias({"aliases": ("GHSA-5678",)}) == "GHSA-5678"

    # Test with set
    assert _extract_alias({"aliases": {"GHSA-9012"}}) != ""  # Set order is unpredictable

    # Test with non-iterable
    assert _extract_alias({"aliases": "not-a-list"}) == ""

    # Test with missing aliases
    assert _extract_alias({}) == ""


def test_iter_vulns_with_edge_cases() -> None:
    """Test _iter_vulns with various edge cases."""
    from issuesuite.pip_audit_integration import _iter_vulns  # noqa: PLC0415

    # Test with non-list vulns
    findings = list(_iter_vulns({"name": "pkg", "version": "1.0", "vulns": "not-a-list"}))
    assert findings == []

    # Test with non-dict vuln entries
    findings = list(_iter_vulns({"name": "pkg", "version": "1.0", "vulns": ["string", 123]}))
    assert findings == []

    # Test with vuln having fixed_versions as non-iterable
    entry = {
        "name": "test-pkg",
        "version": "1.0",
        "vulns": [
            {
                "id": "GHSA-test",
                "description": "Test vuln",
                "fixed_versions": "2.0",  # Not a list
            }
        ],
    }
    findings = list(_iter_vulns(entry))
    assert len(findings) == 1
    assert findings[0].fixed_versions == ()
