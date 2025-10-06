"""Resilient pip-audit integration with offline advisory fallback.

This module wires IssueSuite's curated advisory dataset into pip-audit so
release automation can continue to rely on the upstream CLI while still
succeeding on hermetic builders.  The wrapper installs a patched
``VulnerabilityServiceChoice`` that returns :class:`ResilientPyPIService`
for the ``pypi`` backend.  The resilient service attempts the real PyPI
vulnerability feed first and then falls back to the offline advisories
when requests fail or return incomplete data.

The module also exposes ``run_resilient_pip_audit`` which can be used by
quality-gate automation (and the ``issuesuite security`` CLI command) to
invoke pip-audit programmatically with the patch installed.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from collections import defaultdict
from collections.abc import Callable, Iterator, MutableMapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import requests
from packaging.utils import canonicalize_name
from packaging.version import Version

from .dependency_audit import (
    Advisory,
    Auditor,
    Finding,
    OnlineAuditUnavailableError,
    PipSource,
    _dependency_version,
    load_advisories,
)

pip_audit_audit: Callable[..., object] | None = None
VulnerabilityServiceChoice: Any = None
PipAuditConnectionError: type[Exception] = Exception
ServiceError: type[Exception] = Exception
Dependency: Any = None
ResolvedDependency: Any = None
VulnerabilityResult: Any = None
PyPIService: Any = None

try:  # pragma: no cover - exercised in integration tests
    _cli_mod = import_module("pip_audit._cli")
    _interface_mod = import_module("pip_audit._service.interface")
    _pypi_mod = import_module("pip_audit._service.pypi")
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    pass
else:
    VulnerabilityServiceChoice = _cli_mod.VulnerabilityServiceChoice
    pip_audit_audit = _cli_mod.audit
    PipAuditConnectionError = _interface_mod.ConnectionError
    Dependency = _interface_mod.Dependency
    ResolvedDependency = _interface_mod.ResolvedDependency
    ServiceError = _interface_mod.ServiceError
    VulnerabilityResult = _interface_mod.VulnerabilityResult
    PyPIService = _pypi_mod.PyPIService

try:  # pragma: no cover - optional telemetry support
    from .observability import get_tracer as _imported_get_tracer
except Exception:  # pragma: no cover - telemetry disabled
    _get_tracer: Callable[[str], Any] | None = None
else:
    _get_tracer = _imported_get_tracer


def _start_telemetry_span(name: str) -> contextlib.AbstractContextManager[Any]:
    if _get_tracer is None:
        return contextlib.nullcontext(None)
    try:
        tracer = _get_tracer("issuesuite.security")
    except Exception:
        return contextlib.nullcontext(None)
    span_cm = tracer.start_as_current_span(name)
    return cast(contextlib.AbstractContextManager[Any], span_cm)

LOGGER = logging.getLogger(__name__)


@dataclass
class _OfflineResult:
    """Internal helper capturing offline vulnerability data."""

    advisory: Advisory
    fix_versions: tuple[Version, ...]


class ResilientPyPIService(PyPIService):
    """PyPI vulnerability service with curated offline fallback."""

    def __init__(
        self,
        cache_dir: Path | None,
        timeout: int | None,
        *,
        advisories: Sequence[Advisory] | None = None,
    ) -> None:
        super().__init__(cache_dir=cache_dir, timeout=timeout)
        advice = advisories if advisories is not None else load_advisories()
        index: MutableMapping[str, list[_OfflineResult]] = defaultdict(list)
        for advisory in advice:
            canonical = canonicalize_name(advisory.package)
            fix_versions = tuple(Version(v) for v in advisory.fixed_versions)
            index[canonical].append(_OfflineResult(advisory=advisory, fix_versions=fix_versions))
        self._advisories = {name: tuple(entries) for name, entries in index.items()}
        self._fallback_events: list[str] = []

    @property
    def fallback_events(self) -> Sequence[str]:
        """Return recorded fallback log messages (for testing/diagnostics)."""

        return tuple(self._fallback_events)

    def _iter_offline_matches(
        self, spec: Any
    ) -> Iterator[tuple[_OfflineResult, Any]]:
        entries = self._advisories.get(spec.canonical_name, ())
        for entry in entries:
            if entry.advisory.specifiers.contains(str(spec.version), prereleases=True):
                result = VulnerabilityResult(
                    id=entry.advisory.vulnerability_id,
                    description=entry.advisory.description,
                    fix_versions=list(entry.fix_versions),
                    aliases=set(),
                    published=None,
                )
                yield entry, result

    def _record_fallback(self, spec: Any, reason: Exception) -> None:
        message = (
            f"PyPI vulnerability feed unavailable for {spec.name} {spec.version} ({reason}); "
            "using offline advisories"
        )
        LOGGER.warning(message)
        self._fallback_events.append(message)
        with _start_telemetry_span("issuesuite.pip_audit.fallback") as span:
            if span is not None:
                try:
                    span.set_attribute("issuesuite.package", spec.name)
                    span.set_attribute("issuesuite.version", str(spec.version))
                    span.set_attribute("issuesuite.fallback_reason", type(reason).__name__)
                except Exception:
                    LOGGER.debug("Failed to record telemetry attributes for pip-audit fallback")

    def query(self, spec: Any) -> tuple[Any, list[Any]]:
        if spec.is_skipped():
            return spec, []
        resolved = spec

        try:
            dependency, results = super().query(resolved)
        except (requests.RequestException, PipAuditConnectionError, ServiceError) as exc:
            offline_results = [offline for _, offline in self._iter_offline_matches(resolved)]
            if offline_results:
                self._record_fallback(resolved, exc)
                return resolved, offline_results
            self._record_fallback(resolved, exc)
            return resolved, []

        offline_results = [offline for _, offline in self._iter_offline_matches(resolved)]
        if offline_results:
            known_ids = {result.id for result in results}
            for offline in offline_results:
                if offline.id not in known_ids:
                    results.append(offline)
        return dependency, results


def collect_online_findings() -> list[Finding]:
    """Collect findings using the resilient PyPI service."""

    if Auditor is None or PipSource is None or PyPIService is None:
        raise OnlineAuditUnavailableError("pip-audit is not installed")

    try:
        service = ResilientPyPIService(cache_dir=None, timeout=None)
        auditor = Auditor(service)
        source = PipSource(local=True, skip_editable=True)
        findings: list[Finding] = []
        for dependency, vulnerabilities in auditor.audit(source):
            if dependency.is_skipped() or not vulnerabilities:
                continue
            dependency_version = _dependency_version(dependency)
            for vulnerability in vulnerabilities:
                findings.append(
                    Finding(
                        package=dependency.name.lower(),
                        installed_version=str(dependency_version),
                        vulnerability_id=vulnerability.id,
                        description=vulnerability.description,
                        fixed_versions=tuple(str(version) for version in vulnerability.fix_versions),
                        source="pip-audit",
                    )
                )
        return findings
    except Exception as exc:  # pragma: no cover - exercised via integration tests
        raise OnlineAuditUnavailableError(str(exc)) from exc


def install_resilient_pip_audit(
    *, advisories: Sequence[Advisory] | None = None
) -> Callable[[], None]:
    """Monkey-patch pip-audit so the PyPI backend gains offline fallback."""

    if VulnerabilityServiceChoice is None or PyPIService is None:
        def _noop() -> None:  # pragma: no cover - executed when pip-audit missing
            return None

        return _noop

    original = VulnerabilityServiceChoice.to_service

    def _patched(self: Any, timeout: int, cache_dir: Any) -> Any:
        if self is VulnerabilityServiceChoice.Pypi:
            return ResilientPyPIService(cache_dir, timeout, advisories=advisories)
        return original(self, timeout, cache_dir)

    VulnerabilityServiceChoice.to_service = _patched

    def _restore() -> None:
        VulnerabilityServiceChoice.to_service = original

    return _restore


@contextlib.contextmanager
def _temporary_argv(argv: Sequence[str]) -> Iterator[None]:
    original = sys.argv[:]
    sys.argv = list(argv)
    try:
        yield
    finally:
        sys.argv = original


def run_resilient_pip_audit(arguments: Sequence[str] | None = None) -> int:
    """Invoke pip-audit with offline fallback enabled.

    Parameters
    ----------
    arguments:
        Optional CLI arguments excluding the executable name. When omitted the
        current ``sys.argv`` is used.
    """

    install_resilient_pip_audit()

    if VulnerabilityServiceChoice is None or PyPIService is None or pip_audit_audit is None:
        LOGGER.warning("pip-audit is not installed; skipping online vulnerability probe")
        return 0

    argv: list[str]
    if arguments is None:
        argv = sys.argv[:]
        if not argv:
            argv = ["pip-audit"]
    else:
        argv = ["pip-audit", *arguments]

    with _temporary_argv(argv):
        try:
            pip_audit_audit()
        except SystemExit as exc:  # pragma: no cover - exercised via CLI smoke tests
            code = int(exc.code or 0)
            return code
    return 0


def main() -> None:
    """Console script entrypoint wrapping pip-audit with the resilient service."""

    exit_code = run_resilient_pip_audit()
    raise SystemExit(exit_code)
