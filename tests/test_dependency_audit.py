from __future__ import annotations

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from issuesuite.dependency_audit import (
    Advisory,
    Finding,
    InstalledPackage,
    OnlineAuditUnavailableError,
    evaluate_advisories,
    perform_audit,
)


def test_evaluate_advisories_flags_vulnerable_package() -> None:
    advisories = [
        Advisory(
            package="demo",
            specifiers=SpecifierSet("<2.0"),
            vulnerability_id="TEST-1",
            description="demo vuln",
            severity="high",
            fixed_versions=("2.0",),
            reference=None,
        )
    ]
    packages = [InstalledPackage(name="demo", version=Version("1.5"))]

    findings = evaluate_advisories(packages, advisories)

    assert findings == [
        Finding(
            package="demo",
            installed_version="1.5",
            vulnerability_id="TEST-1",
            description="demo vuln",
            fixed_versions=("2.0",),
            source="offline-advisory",
        )
    ]


def test_evaluate_advisories_skips_non_matching_version() -> None:
    advisories = [
        Advisory(
            package="demo",
            specifiers=SpecifierSet("<2.0"),
            vulnerability_id="TEST-1",
            description="demo vuln",
            severity="high",
            fixed_versions=("2.0",),
            reference=None,
        )
    ]
    packages = [InstalledPackage(name="demo", version=Version("2.1"))]

    assert evaluate_advisories(packages, advisories) == []


def test_perform_audit_falls_back_when_online_unavailable() -> None:
    advisories = [
        Advisory(
            package="demo",
            specifiers=SpecifierSet("<2.0"),
            vulnerability_id="TEST-1",
            description="demo vuln",
            severity="high",
            fixed_versions=("2.0",),
            reference=None,
        )
    ]
    packages = [InstalledPackage(name="demo", version=Version("1.0"))]

    def failing_online() -> list[Finding]:
        raise OnlineAuditUnavailableError("network down")

    findings, fallback_reason = perform_audit(
        advisories=advisories,
        packages=packages,
        online_collector=failing_online,
    )

    assert fallback_reason == "network down"
    assert len(findings) == 1
    assert findings[0].source == "offline-advisory"
