"""Integration helpers for ``pip-audit`` and telemetry-aware wrappers."""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import json
import os
import shlex
import subprocess  # nosec B404 - subprocess orchestrates pip-audit execution
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Protocol, cast

from packaging.version import Version

from .dependency_audit import (
    Advisory,
    Finding,
    InstalledPackage,
    collect_installed_packages,
    evaluate_advisories,
    load_advisories,
    perform_audit,
    render_findings_table,
)

_otel_trace: ModuleType | None
_otel_spec = importlib.util.find_spec("opentelemetry.trace")
if _otel_spec is not None:  # pragma: no cover - optional dependency
    _otel_trace = importlib.import_module("opentelemetry.trace")
else:  # pragma: no cover
    _otel_trace = None

try:
    _pip_audit_spec = importlib.util.find_spec("pip_audit._cli")
except ModuleNotFoundError:  # pragma: no cover - optional dependency absent
    _pip_audit_spec = None
if _pip_audit_spec is not None:  # pragma: no cover - optional dependency
    _pip_cli = importlib.import_module("pip_audit._cli")
    VulnerabilityServiceChoice = getattr(_pip_cli, "VulnerabilityServiceChoice", None)
else:  # pragma: no cover
    VulnerabilityServiceChoice = None

ResolvedDependencyType = Any

_PIP_AUDIT_BIN = os.environ.get("PIP_AUDIT_BIN", "pip-audit")
_PIP_AUDIT_TIMEOUT_ENV = "ISSUESUITE_PIP_AUDIT_TIMEOUT"
_PIP_AUDIT_SUPPRESS_TABLE_ENV = "ISSUESUITE_PIP_AUDIT_SUPPRESS_TABLE"


def _get_tracer(name: str) -> _TracerLike:
    module = _otel_trace
    if module is None:  # pragma: no cover - telemetry optional
        return _NoopTracer()
    return cast(_TracerLike, module.get_tracer(name))


class _NoopSpan:
    def set_attribute(self, *_: object, **__: object) -> None:  # pragma: no cover
        return None


class _SpanLike(Protocol):
    def set_attribute(self, key: str, value: str) -> None: ...


class _TracerLike(Protocol):
    def start_as_current_span(self, name: str) -> contextlib.AbstractContextManager[_SpanLike]: ...


class _SpanContext(contextlib.AbstractContextManager[_SpanLike]):
    def __enter__(self) -> _SpanLike:  # pragma: no cover
        return _NoopSpan()

    def __exit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> None:  # pragma: no cover
        return None


class _NoopTracer:
    def start_as_current_span(
        self, name: str
    ) -> contextlib.AbstractContextManager[_SpanLike]:  # pragma: no cover
        del name
        return _SpanContext()


@dataclass(frozen=True)
class _ServiceFinding:
    id: str
    description: str
    fix_versions: tuple[str, ...]
    source: str

    @classmethod
    def from_finding(cls, finding: Finding) -> _ServiceFinding:
        return cls(
            id=finding.vulnerability_id,
            description=finding.description,
            fix_versions=finding.fixed_versions,
            source=finding.source,
        )


class _Session:
    """Lightweight session placeholder to allow monkeypatching in tests."""

    def get(self, *_: Any, **__: Any) -> Any:  # pragma: no cover - default offline mode
        raise RuntimeError("network access disabled")


class ResilientPyPIService:
    """Minimal drop-in replacement for pip-audit's PyPI service.

    The implementation intentionally avoids depending on pip-audit internals so
    that the module stays importable even when the optional dependency is not
    installed. Tests interact with the API surface in a narrow fashion (query
    returning ``(dependency, Iterable[Result])`` and recording fallback events),
    which this implementation mirrors.
    """

    def __init__(
        self,
        *,
        cache_dir: str | None,
        timeout: float | None,
        advisories: Iterable[Advisory] | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.timeout = timeout
        self._advisories = list(advisories or [])
        self.fallback_events: list[str] = []
        self.session = _Session()

    def _evaluate_offline(self, dependency: ResolvedDependencyType) -> list[_ServiceFinding]:
        name = str(getattr(dependency, "name", "")).lower().replace("_", "-")
        version_value = getattr(dependency, "version", "0")
        try:
            version = Version(str(version_value))
        except Exception:  # pragma: no cover - invalid metadata fallback
            version = Version("0")
        package = InstalledPackage(name=name, version=version)
        findings = evaluate_advisories([package], self._advisories)
        return [_ServiceFinding.from_finding(finding) for finding in findings]

    def _record_fallback(self, dependency: ResolvedDependencyType, error: Exception) -> None:
        self.fallback_events.append(str(error))
        tracer = _get_tracer("issuesuite.pip_audit")
        with tracer.start_as_current_span("issuesuite.pip_audit.fallback") as span:
            span.set_attribute("issuesuite.package", str(getattr(dependency, "name", "unknown")))
            span.set_attribute("issuesuite.error", str(error))

    def query(
        self, dependency: ResolvedDependencyType
    ) -> tuple[ResolvedDependencyType, list[_ServiceFinding]]:
        tracer = _get_tracer("issuesuite.pip_audit")
        with tracer.start_as_current_span("issuesuite.pip_audit.query") as span:
            span.set_attribute("issuesuite.package", str(getattr(dependency, "name", "unknown")))
        results: list[_ServiceFinding] = []
        try:
            response = self.session.get(
                "https://pypi.org/pypi/{name}/{version}/json".format(
                    name=getattr(dependency, "name", ""),
                    version=getattr(dependency, "version", ""),
                ),
                timeout=self.timeout,
            )
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            payload: Any = response.json() if hasattr(response, "json") else {}
            findings = list(_extract_findings(payload))
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            self._record_fallback(dependency, exc)
            findings = []
        results.extend(_ServiceFinding.from_finding(item) for item in findings)
        results.extend(self._evaluate_offline(dependency))
        return dependency, results


def install_resilient_pip_audit(
    *, advisories: Iterable[Advisory] | None = None
) -> Callable[[], None]:
    """Patch pip-audit to use :class:`ResilientPyPIService`.

    Returns a callable that restores the previous ``to_service`` behaviour.
    When pip-audit is not available the installer becomes a no-op.
    """

    if VulnerabilityServiceChoice is None:  # pragma: no cover
        return lambda: None

    choice = VulnerabilityServiceChoice.Pypi
    original = choice.to_service

    def _patched(
        self: Any,
        *,
        timeout: float | None = None,
        cache_dir: str | None = None,
        **_: object,
    ) -> ResilientPyPIService:
        return ResilientPyPIService(
            cache_dir=cache_dir,
            timeout=timeout,
            advisories=advisories,
        )

    choice.to_service = _patched.__get__(choice, type(choice))

    def _restore() -> None:
        choice.to_service = original

    return _restore


class PipAuditError(RuntimeError):
    """Raised when ``pip-audit`` cannot be executed successfully."""


def _resolve_timeout() -> float | None:
    raw = os.environ.get(_PIP_AUDIT_TIMEOUT_ENV)
    if raw is None:
        return 60.0
    try:
        value = float(raw)
    except ValueError:
        return 60.0
    return None if value <= 0 else value


def _run_pip_audit(
    args: Sequence[str], *, capture: bool, timeout: float | None
) -> subprocess.CompletedProcess[str]:
    command = [_PIP_AUDIT_BIN, *args]
    env = os.environ.copy()
    env.setdefault("PIP_AUDIT_PROGRESS_BAR", "off")
    try:
        return subprocess.run(  # noqa: S603 - user-invoked binary  # nosec B603 - controlled arguments from trusted config
            command,
            check=False,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - runtime dependent
        raise PipAuditError(
            f"pip-audit timed out after {timeout:.0f}s"
            if timeout is not None
            else "pip-audit timed out"
        ) from exc
    except FileNotFoundError as exc:  # pragma: no cover - environment dependent
        raise PipAuditError(f"{_PIP_AUDIT_BIN!r} executable not found") from exc


def _normalise_text(value: object) -> str:
    return str(value) if value is not None else ""


def _iter_entries(payload: object) -> Iterable[dict[str, object]]:
    if isinstance(payload, dict):
        entries = payload.get("vulnerabilities") or payload.get("dependencies") or []
    else:
        entries = payload or []
    if not isinstance(entries, list):
        return []
    return (entry for entry in entries if isinstance(entry, dict))


def _normalise_name(value: object) -> str:
    return _normalise_text(value).lower().replace("_", "-")


def _extract_alias(vuln: dict[str, object]) -> str:
    aliases = vuln.get("aliases")
    if isinstance(aliases, (list, tuple, set)):
        return _normalise_text(next(iter(aliases), ""))
    return ""


def _iter_vulns(entry: dict[str, object]) -> Iterable[Finding]:
    name = _normalise_name(entry.get("name"))
    version = _normalise_text(entry.get("version")) or "0"
    vulns = entry.get("vulns")
    if not isinstance(vulns, list):
        return []

    findings: list[Finding] = []
    for vuln in vulns:
        if not isinstance(vuln, dict):
            continue
        vuln_id = _normalise_text(vuln.get("id")) or _extract_alias(vuln) or "unknown"
        description = _normalise_text(vuln.get("description")) or _normalise_text(
            vuln.get("details")
        )
        fixed_versions = vuln.get("fix_versions") or vuln.get("fixed_versions") or []
        if isinstance(fixed_versions, (list, tuple, set)):
            fixed = tuple(str(item) for item in fixed_versions)
        else:
            fixed = ()
        findings.append(
            Finding(
                package=name,
                installed_version=version,
                vulnerability_id=vuln_id,
                description=description,
                fixed_versions=fixed,
                source="pip-audit",
            )
        )
    return findings


def _extract_findings(payload: object) -> Iterable[Finding]:
    findings: list[Finding] = []
    for entry in _iter_entries(payload):
        findings.extend(_iter_vulns(entry))
    return findings


def collect_online_findings(
    packages: Sequence[InstalledPackage] | None = None,
) -> Iterable[Finding]:
    """Collect findings by delegating to ``pip-audit``.

    The ``packages`` argument remains optional; when provided it filters the
    resulting findings to the requested package names.
    """

    packages = packages or []
    target_packages = {pkg.canonical_name for pkg in packages}
    args = ["--format", "json", "--progress-spinner", "off"]
    result = _run_pip_audit(args, capture=True, timeout=_resolve_timeout())
    if result.returncode not in (0, 1):
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        raise PipAuditError(f"pip-audit exited with code {result.returncode}: {stderr}")
    try:
        payload = json.loads(result.stdout or "[]") if result.stdout else []
    except json.JSONDecodeError as exc:
        raise PipAuditError("Failed to parse pip-audit JSON output") from exc
    findings = list(_extract_findings(payload))
    if target_packages:
        findings = [item for item in findings if item.package in target_packages]
    return findings


_SSL_ERROR_PATTERNS = tuple(
    pattern.lower()
    for pattern in (
        "SSLError",
        "CERTIFICATE_VERIFY_FAILED",
        "HTTPSConnectionPool",
        "MaxRetryError",
    )
)

_MISSING_DEPENDENCY_PATTERNS = ("dependency not found on pypi",)


def _detect_recoverable_failure(stdout: str, stderr: str) -> str | None:
    combined = f"{stdout}\n{stderr}".lower()
    for reason, patterns in (
        ("ssl-error", _SSL_ERROR_PATTERNS),
        ("missing-dependency", _MISSING_DEPENDENCY_PATTERNS),
    ):
        if any(token in combined for token in patterns):
            return reason
    return None


def _should_emit_offline_table() -> bool:
    return os.environ.get(_PIP_AUDIT_SUPPRESS_TABLE_ENV) != "1"


def _run_offline_advisory_scan(reason: str) -> int:
    print(
        f"[security] pip-audit unavailable ({reason}); falling back to offline advisories.",
        file=sys.stderr,
    )
    advisories = load_advisories()
    packages = collect_installed_packages()
    findings, _ = perform_audit(
        advisories=advisories,
        packages=packages,
        online_probe=False,
    )
    if _should_emit_offline_table():
        print(render_findings_table(findings))
    return 0 if not findings else 1


def run_resilient_pip_audit(args: Sequence[str]) -> int:
    """Execute ``pip-audit`` while providing actionable diagnostics."""

    base_args = ["--progress-spinner", "off"]
    argv = [*base_args, *args]
    try:
        result = _run_pip_audit(argv, capture=True, timeout=_resolve_timeout())
    except PipAuditError as exc:
        return _run_offline_advisory_scan(str(exc))
    stdout_text = result.stdout or ""
    stderr_text = result.stderr or ""
    if result.returncode == 1:
        reason = _detect_recoverable_failure(stdout_text, stderr_text)
        if reason is not None:
            return _run_offline_advisory_scan(reason)
    if result.returncode not in (0, 1):
        command = " ".join(shlex.quote(arg) for arg in ([_PIP_AUDIT_BIN] + list(argv)))
        print(
            f"[security] pip-audit command failed (rc={result.returncode}): {command}",
            file=sys.stderr,
        )
        return _run_offline_advisory_scan(f"rc={result.returncode}")
    if stdout_text:
        sys.stdout.write(stdout_text)
        if not stdout_text.endswith("\n"):
            sys.stdout.write("\n")
    if stderr_text:
        sys.stderr.write(stderr_text)
        if not stderr_text.endswith("\n"):
            sys.stderr.write("\n")
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    return run_resilient_pip_audit(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "ResilientPyPIService",
    "install_resilient_pip_audit",
    "PipAuditError",
    "collect_online_findings",
    "run_resilient_pip_audit",
    "main",
]
