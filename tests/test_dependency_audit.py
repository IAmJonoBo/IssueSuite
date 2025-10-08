from __future__ import annotations

import json
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from issuesuite.dependency_audit import (
    Advisory,
    Finding,
    InstalledPackage,
    OnlineAuditUnavailableError,
    _render_table,
    evaluate_advisories,
    main,
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


def test_render_table_formats_rows() -> None:
    findings = [
        Finding(
            package="demo",
            installed_version="1.0",
            vulnerability_id="TEST-1",
            description="",  # description unused in table
            fixed_versions=("2.0",),
            source="pip-audit",
        )
    ]
    table = _render_table(findings)
    assert "Package" in table
    assert "demo" in table
    assert "pip-audit" in table


def test_main_outputs_json_when_requested(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    advisories = [
        {
            "package": "demo",
            "specifiers": "<2.0",
            "id": "TEST-1",
            "description": "demo vuln",
            "severity": "high",
            "fixed_in": ["2.0"],
        }
    ]
    advisory_path = tmp_path / "advisories.json"
    advisory_path.write_text(json.dumps({"advisories": advisories}))

    monkeypatch.setattr(
        "issuesuite.dependency_audit.collect_installed_packages",
        lambda: [InstalledPackage(name="demo", version=Version("1.5"))],
    )
    monkeypatch.setattr(
        "issuesuite.dependency_audit._collect_online_findings",
        lambda: [
            Finding(
                package="demo",
                installed_version="1.5",
                vulnerability_id="TEST-ONLINE",
                description="",
                fixed_versions=(),
                source="pip-audit",
            )
        ],
    )

    exit_code = main(["--advisories", str(advisory_path), "--output-json"])
    assert exit_code == 1


def test_main_handles_offline_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "issuesuite.dependency_audit.collect_installed_packages",
        lambda: [InstalledPackage(name="demo", version=Version("1.5"))],
    )
    monkeypatch.setattr(
        "issuesuite.dependency_audit.load_advisories",
        lambda path=None: [
            Advisory(
                package="demo",
                specifiers=SpecifierSet("<2.0"),
                vulnerability_id="TEST-1",
                description="demo vuln",
                severity="high",
                fixed_versions=("2.0",),
                reference=None,
            )
        ],
    )

    exit_code = main(["--offline-only"])
    captured = capsys.readouterr()
    assert "demo" in captured.out
    assert exit_code == 1
