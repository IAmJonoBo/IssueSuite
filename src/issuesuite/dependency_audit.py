"""Offline-friendly dependency vulnerability auditing utilities."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import import_module, metadata, resources
from pathlib import Path
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import Version

try:  # pragma: no cover - pip-audit is optional during tests
    _audit_mod = import_module('pip_audit._audit')
    _source_mod = import_module('pip_audit._dependency_source.pip')
    _interface_mod = import_module('pip_audit._service.interface')
    _pypi_mod = import_module('pip_audit._service.pypi')
except ModuleNotFoundError:  # pragma: no cover
    Auditor: Any = None
    PipSource: Any = None
    Dependency: Any = None
    PyPIService: Any = None
else:
    Auditor = _audit_mod.Auditor
    PipSource = _source_mod.PipSource
    Dependency = _interface_mod.Dependency
    PyPIService = _pypi_mod.PyPIService


@dataclass(frozen=True)
class Advisory:
    """Represents an offline advisory sourced from `security_advisories.json`."""

    package: str
    specifiers: SpecifierSet
    vulnerability_id: str
    description: str
    severity: str | None
    fixed_versions: tuple[str, ...]
    reference: str | None


@dataclass(frozen=True)
class InstalledPackage:
    """Simplified representation of an installed distribution."""

    name: str
    version: Version


@dataclass(frozen=True)
class Finding:
    """Represents a vulnerability discovered during an audit."""

    package: str
    installed_version: str
    vulnerability_id: str
    description: str
    fixed_versions: tuple[str, ...]
    source: str


class OnlineAuditUnavailableError(RuntimeError):
    """Raised when the online pip-audit step is unavailable."""


def _load_advisory_payload(path: Path | None = None) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    resource = resources.files("issuesuite.data").joinpath("security_advisories.json")
    return resource.read_text(encoding="utf-8")


def load_advisories(path: Path | None = None) -> list[Advisory]:
    """Load advisory definitions from disk or package resources."""

    payload = json.loads(_load_advisory_payload(path))
    advisories: list[Advisory] = []
    for entry in payload.get("advisories", []):
        advisories.append(
            Advisory(
                package=entry["package"].lower(),
                specifiers=SpecifierSet(entry["specifiers"]),
                vulnerability_id=entry["id"],
                description=entry.get("description", ""),
                severity=entry.get("severity"),
                fixed_versions=tuple(entry.get("fixed_in", [])),
                reference=entry.get("reference"),
            )
        )
    return advisories


def collect_installed_packages() -> list[InstalledPackage]:
    packages: list[InstalledPackage] = []
    for dist in metadata.distributions():
        try:
            name = dist.metadata["Name"].lower()
        except KeyError:  # pragma: no cover - extremely rare metadata omission
            continue
        packages.append(InstalledPackage(name=name, version=Version(dist.version)))
    return packages


def evaluate_advisories(
    packages: Sequence[InstalledPackage], advisories: Sequence[Advisory]
) -> list[Finding]:
    """Evaluate offline advisories against installed packages."""

    by_name: dict[str, InstalledPackage] = {pkg.name: pkg for pkg in packages}
    findings: list[Finding] = []
    for advisory in advisories:
        package = by_name.get(advisory.package)
        if package is None:
            continue
        if advisory.specifiers.contains(str(package.version), prereleases=True):
            findings.append(
                Finding(
                    package=package.name,
                    installed_version=str(package.version),
                    vulnerability_id=advisory.vulnerability_id,
                    description=advisory.description,
                    fixed_versions=advisory.fixed_versions,
                    source="offline-advisory",
                )
            )
    return findings


def _collect_online_findings() -> list[Finding]:
    if Auditor is None or PyPIService is None or PipSource is None:
        raise OnlineAuditUnavailableError("pip-audit is not installed")
    try:
        service = PyPIService()
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
    except Exception as exc:  # pragma: no cover - exercised via integration
        raise OnlineAuditUnavailableError(str(exc)) from exc


def _dependency_version(dependency: Any) -> Version:
    version = getattr(dependency, "version", None)
    if version is None:
        raise OnlineAuditUnavailableError(f"Dependency {dependency.name} missing version")
    return Version(str(version))


def perform_audit(
    *,
    advisories: Sequence[Advisory],
    packages: Sequence[InstalledPackage],
    online_probe: bool = True,
    online_collector: Callable[[], Sequence[Finding]] = _collect_online_findings,
) -> tuple[list[Finding], str | None]:
    """Audit dependencies, optionally attempting an online scan first."""

    findings: list[Finding] = []
    fallback_reason: str | None = None
    if online_probe:
        try:
            findings.extend(online_collector())
        except OnlineAuditUnavailableError as exc:
            fallback_reason = str(exc)
    findings.extend(evaluate_advisories(packages, advisories))
    deduped: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.package, finding.vulnerability_id)
        deduped.setdefault(key, finding)
    return list(deduped.values()), fallback_reason


def _render_table(findings: Sequence[Finding]) -> str:
    if not findings:
        return "No known vulnerabilities detected."
    headers = ("Package", "Installed", "Vulnerability", "Source")
    rows = [headers]
    for finding in findings:
        rows.append(
            (
                finding.package,
                finding.installed_version,
                finding.vulnerability_id,
                finding.source,
            )
        )
    column_widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]
    lines: list[str] = []
    for row in rows:
        padded = [cell.ljust(column_widths[idx]) for idx, cell in enumerate(row)]
        lines.append("  ".join(padded))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit dependencies with offline fallback")
    parser.add_argument(
        "--advisories",
        type=Path,
        help="Optional override path for advisory dataset",
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Skip online pip-audit probe and rely solely on offline advisories",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Emit machine-readable JSON summary",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    advisories = load_advisories(args.advisories)
    packages = collect_installed_packages()
    findings, fallback_reason = perform_audit(
        advisories=advisories,
        packages=packages,
        online_probe=not args.offline_only,
    )

    if args.output_json:
        output = {
            "findings": [
                {
                    "package": finding.package,
                    "installed_version": finding.installed_version,
                    "vulnerability_id": finding.vulnerability_id,
                    "description": finding.description,
                    "fixed_versions": list(finding.fixed_versions),
                    "source": finding.source,
                }
                for finding in findings
            ],
            "fallback_reason": fallback_reason,
        }
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(_render_table(findings))
        if fallback_reason:
            print(f"Warning: online audit unavailable ({fallback_reason}).", file=sys.stderr)

    return 0 if not findings else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
