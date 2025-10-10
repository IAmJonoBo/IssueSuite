"""Offline-first dependency audit helpers.

The test suite exercises a higher-level API than the original implementation
exposed, so this module intentionally mirrors that interface:

* ``InstalledPackage`` captures normalized distribution metadata using
  :class:`packaging.version.Version` for rich comparisons.
* ``Advisory`` stores ``SpecifierSet`` instances so callers can construct
  them programmatically while the loader handles JSON payloads.
* ``evaluate_advisories`` produces ``Finding`` objects that unify offline and
  online results.
* ``perform_audit`` merges offline evaluation with an optional online
  collector, surfacing a human-readable fallback reason when online probing
  fails or is explicitly disabled.
* ``main`` implements a small CLI to support ``issuesuite security`` as well as
  targeted unit tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from importlib import metadata
from pathlib import Path
from typing import Any, cast

try:  # pragma: no cover - lazy optional import
    from .pip_audit_integration import collect_online_findings as _pip_collect_online
except Exception:  # pragma: no cover - pip-audit integration optional
    _pip_collect_online = None  # type: ignore[assignment]

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

DEFAULT_ADVISORY_PATH = Path(__file__).with_name("security_advisories.json")
DEFAULT_ALLOWLIST_PATH = Path(__file__).with_name("security_allowlist.json")


class OnlineAuditUnavailableError(RuntimeError):
    """Raised when the online audit cannot be completed."""


@dataclass(frozen=True)
class InstalledPackage:
    """Metadata about an installed distribution."""

    name: str
    version: Version

    @property
    def canonical_name(self) -> str:
        return self.name.lower().replace("_", "-")

    def as_finding_tuple(self) -> tuple[str, str]:
        return (self.canonical_name, str(self.version))


@dataclass(frozen=True)
class Advisory:
    """Represents a single vulnerability advisory."""

    package: str
    specifiers: SpecifierSet
    vulnerability_id: str
    description: str
    severity: str | None = None
    fixed_versions: tuple[str, ...] = ()
    reference: str | None = None

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Advisory:
        package = str(payload.get("package", "")).strip()
        specifiers_raw = payload.get("specifiers") or payload.get("spec")
        if specifiers_raw:
            specifiers = SpecifierSet(str(specifiers_raw))
        else:
            specifiers = SpecifierSet()
        vuln_id = str(payload.get("id") or payload.get("vulnerability_id") or "").strip()
        description = str(payload.get("description") or "").strip()
        severity = payload.get("severity")
        fixed_in_raw = payload.get("fixed_in") or payload.get("fixed_versions") or ()
        fixed_versions: tuple[str, ...]
        if not fixed_in_raw:
            fixed_versions = ()
        elif isinstance(fixed_in_raw, (list, tuple, set)):
            fixed_versions = cast(tuple[str, ...], tuple(str(item) for item in fixed_in_raw))
        else:
            fixed_versions = cast(tuple[str, ...], (str(fixed_in_raw),))
        reference = payload.get("reference") or payload.get("url")
        return cls(
            package=package.lower().replace("_", "-"),
            specifiers=specifiers,
            vulnerability_id=vuln_id,
            description=description,
            severity=str(severity) if severity is not None else None,
            fixed_versions=fixed_versions,
            reference=str(reference) if reference is not None else None,
        )

    def matches(self, package: InstalledPackage) -> bool:
        try:
            return package.canonical_name == self.package and package.version in self.specifiers
        except Exception:  # pragma: no cover - defensive for packaging edge cases
            return False


@dataclass(frozen=True)
class Finding:
    """Combined vulnerability report for CLI rendering and summaries."""

    package: str
    installed_version: str
    vulnerability_id: str
    description: str
    fixed_versions: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class AllowlistedAdvisory:
    """Represents an accepted-risk vulnerability exception."""

    package: str
    vulnerability_id: str
    specifiers: SpecifierSet
    reason: str
    expires: date | None = None
    owner: str | None = None
    reference: str | None = None

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> AllowlistedAdvisory:
        package = str(payload.get("package", "")).strip().lower().replace("_", "-")
        vulnerability_id = str(payload.get("id") or payload.get("vulnerability_id") or "").strip()
        specifiers_raw = payload.get("specifiers") or payload.get("spec")
        specifiers = SpecifierSet(str(specifiers_raw)) if specifiers_raw else SpecifierSet()
        reason = str(payload.get("reason") or "Accepted risk").strip()
        expires_raw = payload.get("expires")
        expires: date | None
        if expires_raw:
            try:
                expires = date.fromisoformat(str(expires_raw))
            except ValueError:
                expires = None
        else:
            expires = None
        owner = str(payload.get("owner") or payload.get("approved_by") or "").strip() or None
        reference = payload.get("reference") or payload.get("url")
        return cls(
            package=package,
            vulnerability_id=vulnerability_id,
            specifiers=specifiers,
            reason=reason,
            expires=expires,
            owner=owner,
            reference=str(reference) if reference is not None else None,
        )

    def matches(self, finding: Finding) -> bool:
        if finding.package != self.package:
            return False
        if self.vulnerability_id and finding.vulnerability_id != self.vulnerability_id:
            return False
        if self.expires and date.today() > self.expires:
            return False
        if not self.specifiers:
            return True
        try:
            version = Version(finding.installed_version)
        except InvalidVersion:
            return False
        return version in self.specifiers


@dataclass(frozen=True)
class SuppressedFinding:
    """Tracks a vulnerability suppressed via the allowlist."""

    finding: Finding
    allowlisted: AllowlistedAdvisory


OfflineCollector = Callable[[Sequence[InstalledPackage]], list[Finding]]
OnlineCollector = Callable[[Sequence[InstalledPackage]], Iterable[Finding]]
FlexibleCollector = OnlineCollector | Callable[[], Iterable[Finding]]


def _deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    seen: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.package, finding.vulnerability_id)
        seen[key] = finding
    return list(seen.values())


def apply_allowlist(
    findings: Sequence[Finding],
    allowlist: Sequence[AllowlistedAdvisory],
) -> tuple[list[Finding], list[SuppressedFinding]]:
    remaining: list[Finding] = []
    suppressed: list[SuppressedFinding] = []
    for finding in findings:
        match = next((entry for entry in allowlist if entry.matches(finding)), None)
        if match is None:
            remaining.append(finding)
        else:
            suppressed.append(SuppressedFinding(finding=finding, allowlisted=match))
    return remaining, suppressed


def collect_installed_packages(
    names: Iterable[str] | None = None,
) -> list[InstalledPackage]:
    """Collect installed packages for auditing.

    The optional ``names`` filter accepts already-normalized identifiers.
    """

    selected = {name.lower() for name in names or ()}
    observed: dict[str, InstalledPackage] = {}
    for dist in metadata.distributions():
        try:
            meta_name = dist.metadata["Name"]
        except Exception:  # pragma: no cover - missing metadata edge cases
            meta_name = None
        name = meta_name or getattr(dist, "name", "")
        if not name:
            continue
        canonical = name.lower().replace("_", "-")
        if selected and canonical not in selected:
            continue
        version_value = dist.version or "0"
        try:
            version = Version(version_value)
        except (
            InvalidVersion,
            TypeError,
            ValueError,
        ):  # pragma: no cover - skip invalid metadata entries
            version = None
        if version is None:
            continue
        observed[canonical] = InstalledPackage(name=canonical, version=version)
    return sorted(observed.values(), key=lambda pkg: pkg.name)


def load_advisories(advisories_path: Path | None = None) -> list[Advisory]:
    path = Path(advisories_path or DEFAULT_ADVISORY_PATH)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - treat as no advisories
        return []
    advisories_raw = payload.get("advisories") if isinstance(payload, dict) else payload
    if not isinstance(advisories_raw, list):
        return []
    advisories: list[Advisory] = []
    for entry in advisories_raw:
        if isinstance(entry, dict):
            advisories.append(Advisory.from_json(entry))
    return advisories


def load_allowlist(path: Path | None = None) -> list[AllowlistedAdvisory]:
    allowlist_path = Path(path or DEFAULT_ALLOWLIST_PATH)
    if not allowlist_path.exists():
        return []
    try:
        payload = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    entries = payload.get("allow") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return []
    allowlist: list[AllowlistedAdvisory] = []
    for entry in entries:
        if isinstance(entry, dict):
            allowlist.append(AllowlistedAdvisory.from_json(entry))
    return allowlist


def evaluate_advisories(
    packages: Sequence[InstalledPackage], advisories: Sequence[Advisory]
) -> list[Finding]:
    findings: list[Finding] = []
    for package in packages:
        for advisory in advisories:
            if advisory.matches(package):
                findings.append(
                    Finding(
                        package=package.canonical_name,
                        installed_version=str(package.version),
                        vulnerability_id=advisory.vulnerability_id,
                        description=advisory.description,
                        fixed_versions=advisory.fixed_versions,
                        source="offline-advisory",
                    )
                )
    return findings


def _collect_online_findings(packages: Sequence[InstalledPackage]) -> list[Finding]:
    if _pip_collect_online is None:
        raise OnlineAuditUnavailableError("pip-audit integration unavailable")
    try:
        return list(_pip_collect_online(packages))
    except Exception as exc:  # pragma: no cover - pip-audit runtime issues
        raise OnlineAuditUnavailableError(str(exc)) from exc


def _invoke_online_collector(
    collector: FlexibleCollector,
    packages: Sequence[InstalledPackage],
) -> tuple[list[Finding], str | None]:
    try:
        return list(cast(OnlineCollector, collector)(packages)), None
    except TypeError:
        pass
    except OnlineAuditUnavailableError as exc:
        return [], str(exc)
    except Exception as exc:  # pragma: no cover - unexpected collector errors
        return [], str(exc)

    try:
        return list(cast(Callable[[], Iterable[Finding]], collector)()), None
    except OnlineAuditUnavailableError as exc:
        return [], str(exc)
    except TypeError as exc:
        return [], str(exc)
    except Exception as exc:  # pragma: no cover - unexpected collector errors
        return [], str(exc)


def perform_audit(
    *,
    advisories: Sequence[Advisory],
    packages: Sequence[InstalledPackage],
    online_probe: bool = True,
    online_collector: OnlineCollector | None = None,
) -> tuple[list[Finding], str | None]:
    offline_findings = evaluate_advisories(packages, advisories)
    findings: list[Finding] = list(offline_findings)
    fallback_reason: str | None = None

    if online_probe:
        collector: FlexibleCollector
        if online_collector is None:
            collector = _collect_online_findings
        else:
            collector = cast(FlexibleCollector, online_collector)
        results, reason = _invoke_online_collector(collector, packages)
        findings.extend(results)
        if reason:
            fallback_reason = reason
    else:
        fallback_reason = "offline-only mode"

    return _deduplicate(findings), fallback_reason


def _render_table(findings: Sequence[Finding]) -> str:
    if not findings:
        return "[security] No known vulnerabilities detected."

    headers = ("Package", "Installed", "Advisory", "Fixed", "Source")
    rows: list[list[str]] = [list(headers)]
    for finding in findings:
        fixed = ", ".join(finding.fixed_versions) or "n/a"
        rows.append(
            [
                finding.package,
                finding.installed_version,
                finding.vulnerability_id,
                fixed,
                finding.source,
            ]
        )
    widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]
    lines: list[str] = []
    for row in rows:
        padded = [col.ljust(widths[idx]) for idx, col in enumerate(row)]
        lines.append("  ".join(padded).rstrip())
    return "\n".join(lines)


def render_findings_table(findings: Sequence[Finding]) -> str:
    return _render_table(findings)


def _emit_allowlist_warnings(suppressed: Sequence[SuppressedFinding]) -> None:
    if not suppressed:
        return
    print("[security] Allowlisted vulnerabilities detected:", file=sys.stderr)
    for item in suppressed:
        allow = item.allowlisted
        parts = [allow.reason]
        if allow.expires:
            parts.append(f"expires {allow.expires.isoformat()}")
        if allow.owner:
            parts.append(f"owner {allow.owner}")
        if allow.reference:
            parts.append(str(allow.reference))
        details = "; ".join(parts)
        print(
            f"  - {item.finding.package} {item.finding.vulnerability_id} ({details})",
            file=sys.stderr,
        )


def _print(msg: str) -> None:
    print(msg)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dependency audit helper")
    parser.add_argument("--advisories", type=str, help="Path to advisories JSON", default=None)
    parser.add_argument("--offline-only", action="store_true", help="Skip online audit")
    parser.add_argument("--output-json", action="store_true", help="Emit findings as JSON")
    args = parser.parse_args(list(argv or []))

    advisories = load_advisories(args.advisories)
    packages = collect_installed_packages()
    findings, fallback_reason = perform_audit(
        advisories=advisories,
        packages=packages,
        online_probe=not args.offline_only,
    )
    allowlist = load_allowlist()
    findings, suppressed = apply_allowlist(findings, allowlist)

    if args.output_json:
        payload = {
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
            "allowlisted": [
                {
                    "package": item.finding.package,
                    "installed_version": item.finding.installed_version,
                    "vulnerability_id": item.finding.vulnerability_id,
                    "reason": item.allowlisted.reason,
                    "expires": (
                        item.allowlisted.expires.isoformat() if item.allowlisted.expires else None
                    ),
                    "owner": item.allowlisted.owner,
                    "reference": item.allowlisted.reference,
                }
                for item in suppressed
            ],
        }
        _print(json.dumps(payload, indent=2))
    else:
        _print(_render_table(findings))
        if fallback_reason:
            print(
                f"[security] Warning: online audit unavailable ({fallback_reason}).",
                file=sys.stderr,
            )
        _emit_allowlist_warnings(suppressed)

    return 0 if not findings else 1


__all__ = [
    "Advisory",
    "InstalledPackage",
    "Finding",
    "AllowlistedAdvisory",
    "SuppressedFinding",
    "OnlineAuditUnavailableError",
    "DEFAULT_ADVISORY_PATH",
    "DEFAULT_ALLOWLIST_PATH",
    "collect_installed_packages",
    "load_advisories",
    "load_allowlist",
    "evaluate_advisories",
    "apply_allowlist",
    "perform_audit",
    "render_findings_table",
    "main",
    "_render_table",
]
