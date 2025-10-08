from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from issuesuite.advisory_refresh import (
    check_dataset_age,
    generate_dataset,
    refresh_advisories,
)
from issuesuite.dependency_audit import Finding


@pytest.fixture
def sample_finding() -> Finding:
    return Finding(
        package="requests",
        installed_version="2.31.0",
        vulnerability_id="GHSA-xxxx-xxxx",
        description="Requests vulnerability",
        fixed_versions=("2.32.0",),
        source="pip-audit",
    )


def _osv_payload() -> dict[str, object]:
    return {
        "summary": "Example vulnerability",
        "severity": [{"type": "CVSS_V3", "score": "7.5"}],
        "references": [{"url": "https://example.test/advisory"}],
        "affected": [
            {
                "package": {"name": "requests"},
                "ranges": [
                    {
                        "events": [
                            {"introduced": "0"},
                            {"fixed": "2.32.0"},
                        ]
                    }
                ],
            }
        ],
    }


def test_generate_dataset_builds_specifiers(sample_finding: Finding) -> None:
    dataset = generate_dataset([sample_finding], fetcher=lambda _: _osv_payload())
    assert dataset["advisories"][0]["specifiers"] == ">=0,<2.32.0"
    assert dataset["advisories"][0]["fixed_in"] == ["2.32.0"]
    assert dataset["advisories"][0]["reference"] == "https://example.test/advisory"


def test_check_dataset_age_raises_when_stale(tmp_path: Path) -> None:
    path = tmp_path / "advisories.json"
    payload = {
        "version": 1,
        "generated": (datetime.now(UTC) - timedelta(days=45)).isoformat().replace("+00:00", "Z"),
        "source": "tests",
        "advisories": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError):
        check_dataset_age(path, max_age_days=30)


def test_refresh_advisories_merges_existing(
    tmp_path: Path, sample_finding: Finding, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "advisories.json"
    existing = {
        "version": 1,
        "generated": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": "tests",
        "advisories": [
            {
                "package": "urllib3",
                "id": "GHSA-xrqq-cpx3-44h2",
                "specifiers": "<1.26.18",
                "description": "urllib3 vulnerability",
                "fixed_in": ["1.26.18"],
            }
        ],
    }
    output.write_text(json.dumps(existing), encoding="utf-8")

    monkeypatch.setattr(
        "issuesuite.advisory_refresh.collect_online_findings",
        lambda: [sample_finding],
    )

    dataset = refresh_advisories(
        output_path=output,
        fetcher=lambda _: _osv_payload(),
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert any(entry["id"] == "GHSA-xrqq-cpx3-44h2" for entry in written["advisories"])
    assert any(entry["id"] == sample_finding.vulnerability_id for entry in written["advisories"])
    assert dataset["advisories"] == written["advisories"]
