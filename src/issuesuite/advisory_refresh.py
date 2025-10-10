"""Offline advisory refresh utilities and freshness checks."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from pathlib import Path
from typing import Any, cast
from datetime import datetime, timedelta, timezone
import requests

from .dependency_audit import Finding
from .pip_audit_integration import collect_online_findings

_DEFAULT_DATASET = Path(__file__).resolve().parent / "data" / "security_advisories.json"
_OSV_URL = "https://api.osv.dev/v1/vulns/{vuln_id}"

Fetcher = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class AdvisoryRecord:
    package: str
    vulnerability_id: str
    specifiers: str
    severity: str | None
    description: str
    fixed_in: tuple[str, ...]
    reference: str | None

    def as_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "package": self.package,
            "id": self.vulnerability_id,
            "specifiers": self.specifiers,
            "description": self.description,
            "fixed_in": list(self.fixed_in),
        }
        if self.severity:
            payload["severity"] = self.severity
        if self.reference:
            payload["reference"] = self.reference
        return payload


def _normalise_generated(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_osv(vulnerability_id: str) -> dict[str, Any]:
    """Fetch vulnerability metadata from the OSV API."""

    response = requests.get(_OSV_URL.format(vuln_id=vulnerability_id), timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OSV response payload must be a mapping")
    return cast(dict[str, Any], payload)


def _extract_reference(osv_payload: dict[str, Any]) -> str | None:
    for ref in osv_payload.get("references", []) or []:
        url = ref.get("url")
        if isinstance(url, str):
            return url
    return None


def _extract_severity(osv_payload: dict[str, Any]) -> str | None:
    severities = osv_payload.get("severity") or []
    if not severities:
        return None
    entry = severities[0]
    if not isinstance(entry, dict):
        return None
    score = entry.get("score")
    if isinstance(score, str):
        return score
    score_num = entry.get("score")
    if isinstance(score_num, (int, float)):
        return str(score_num)
    level = entry.get("type")
    return str(level) if isinstance(level, str) else None


def _format_range(lower: str | None, upper: str | None, *, inclusive_upper: bool = False) -> str:
    clauses: list[str] = []
    if lower and lower not in {"", "0"}:
        clauses.append(f">={lower}")
    else:
        clauses.append(">=0")
    if upper:
        op = "<=" if inclusive_upper else "<"
        clauses.append(f"{op}{upper}")
    return ",".join(clauses)


def _ranges_to_specifiers(ranges: Iterable[dict[str, Any]]) -> list[str]:
    clauses: list[str] = []
    for range_entry in ranges:
        events = range_entry.get("events") or []
        lower: str | None = None
        for event in events:
            if "introduced" in event:
                lower = event.get("introduced")
            if "fixed" in event:
                clauses.append(_format_range(lower, event.get("fixed")))
                lower = None
            if "last_affected" in event:
                clauses.append(
                    _format_range(lower, event.get("last_affected"), inclusive_upper=True)
                )
                lower = None
        if lower is not None:
            clauses.append(_format_range(lower, None))
    return clauses


def _extract_specifiers(osv_payload: dict[str, Any], package: str) -> str:
    affected = osv_payload.get("affected") or []
    clauses: list[str] = []
    for record in affected:
        pkg = record.get("package", {})
        name = pkg.get("name") if isinstance(pkg, dict) else None
        if isinstance(name, str) and name.lower() != package:
            continue
        ranges = record.get("ranges") or []
        clauses.extend(_ranges_to_specifiers(ranges))
        versions = record.get("versions") or []
        for version in versions:
            if isinstance(version, str):
                clauses.append(f"=={version}")
    return " || ".join(sorted(set(clauses))) if clauses else ">=0"


def build_advisory_records(
    findings: Sequence[Finding],
    *,
    fetcher: Fetcher,
) -> list[AdvisoryRecord]:
    records: dict[tuple[str, str], AdvisoryRecord] = {}
    for finding in findings:
        payload = fetcher(finding.vulnerability_id)
        specifiers = _extract_specifiers(payload, finding.package)
        record = AdvisoryRecord(
            package=finding.package,
            vulnerability_id=finding.vulnerability_id,
            specifiers=specifiers,
            severity=_extract_severity(payload),
            description=payload.get("summary") or payload.get("details") or finding.description,
            fixed_in=tuple(finding.fixed_versions),
            reference=_extract_reference(payload),
        )
        records[(record.package, record.vulnerability_id)] = record
    return sorted(records.values(), key=lambda rec: (rec.package, rec.vulnerability_id))


def generate_dataset(
    findings: Sequence[Finding],
    *,
    fetcher: Fetcher = fetch_osv,
    source: str = "IssueSuite Automation",
) -> dict[str, Any]:
    advisories = [record.as_json() for record in build_advisory_records(findings, fetcher=fetcher)]
    return {
        "version": 1,
        "generated": _normalise_generated(datetime.now(timezone.utc)),
        "source": source,
        "advisories": advisories,
    }


def _merge_advisories(
    existing: Sequence[dict[str, Any]], new: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for record in existing:
        package = record.get("package")
        vuln_id = record.get("id")
        if isinstance(package, str) and isinstance(vuln_id, str):
            index[(package, vuln_id)] = dict(record)
    for record in new:
        package = record.get("package")
        vuln_id = record.get("id")
        if isinstance(package, str) and isinstance(vuln_id, str):
            index[(package, vuln_id)] = dict(record)
    return sorted(index.values(), key=lambda rec: (rec["package"], rec["id"]))


def refresh_advisories(
    *,
    output_path: Path | None = None,
    fetcher: Fetcher = fetch_osv,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    """Refresh the offline advisory dataset and write it to disk."""

    output = output_path or _DEFAULT_DATASET
    findings = list(collect_online_findings())
    dataset = generate_dataset(findings, fetcher=fetcher)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        dataset["advisories"] = _merge_advisories(
            existing.get("advisories", []), dataset["advisories"]
        )
    if max_age_days is not None:
        check_dataset_age(dataset, max_age_days=max_age_days)
    output.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    return dataset


def check_dataset_age(
    dataset_or_path: Path | dict[str, Any],
    *,
    max_age_days: int,
) -> None:
    """Ensure the offline advisory dataset is not older than ``max_age_days``."""

    if isinstance(dataset_or_path, Path):
        if not dataset_or_path.exists():
            raise RuntimeError(f"Advisory dataset missing: {dataset_or_path}")
        payload = json.loads(dataset_or_path.read_text(encoding="utf-8"))
    else:
        payload = dataset_or_path
    generated = payload.get("generated")
    if not isinstance(generated, str):
        raise RuntimeError("Advisory dataset missing generated timestamp")
    try:
        timestamp = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"Invalid generated timestamp: {generated}") from exc
    if datetime.now(timezone.utc) - timestamp > timedelta(days=max_age_days):
        raise RuntimeError(
            f"Offline advisories older than {max_age_days} days (generated {generated})"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage IssueSuite offline security advisories",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--check", action="store_true", help="Check dataset freshness and exit")
    parser.add_argument("--refresh", action="store_true", help="Refresh advisories before exiting")
    parser.add_argument("--max-age-days", type=int, default=30, help="Maximum allowed dataset age")
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_DATASET,
        help="Path to the offline advisory dataset",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.check and not args.refresh:
        parser.error("specify --check and/or --refresh")

    try:
        if args.refresh:
            refresh_advisories(output_path=args.output)
        if args.check:
            check_dataset_age(args.output, max_age_days=args.max_age_days)
    except Exception as exc:
        print(f"[advisory-refresh] error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
