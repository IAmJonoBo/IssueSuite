from __future__ import annotations

from pathlib import Path

import pytest

from issuesuite.next_steps_validator import validate_next_steps


def _write_tracker(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "Next Steps.md"
    path.write_text(content, encoding="utf-8")
    return path


def _baseline_content() -> str:
    return """\
# Next Steps

## Tasks

- [x] Owner: Assistant (Due: 2025-10-12) — Frontier quality gates uplift with UX and GitHub Projects alignment.

## Steps

- [x] Drafted governance updates aligning UX review lanes with GitHub Projects automation.

## Deliverables

- [x] Publish validator and scripts ensuring coverage thresholds and governance checks.

## Quality Gates

- [x] Coverage ≥80% enforced via `pytest --cov=issuesuite --cov-report=term --cov-report=xml` with `python scripts/quality_gates.py`.
- [x] Static analysis: `ruff check`, `ruff format --check`, and `mypy src`.
- [x] Security: `python -m bandit -r src`, `python -m pip_audit --progress-spinner off --strict`, and `python -m issuesuite.dependency_audit --offline-only`.
- [x] Secrets & governance: `python -m detect_secrets scan --baseline .secrets.baseline` and `python scripts/verify_next_steps.py`.
- [x] Build & runtime: `python -m compileall src`, `python -m build`, `python scripts/generate_performance_report.py`, and `python -m issuesuite.benchmarking --check --report performance_report.json`.
- [x] Advisories: `python -m issuesuite.advisory_refresh --check --max-age-days 30`.

## Links

- [x] GitHub Projects alignment documented in governance tracker.

## Risks / Notes

- [x] UX research cadence documented alongside GitHub Projects automation notes.
"""


def test_validate_next_steps_accepts_compliant_tracker(tmp_path: Path) -> None:
    tracker = _write_tracker(tmp_path, _baseline_content())
    # Should not raise.
    validate_next_steps([tracker])


def test_validate_next_steps_rejects_missing_quality_gate(tmp_path: Path) -> None:
    tracker = _write_tracker(
        tmp_path, _baseline_content().replace("ruff format --check", "ruff")
    )
    with pytest.raises(ValueError) as exc:
        validate_next_steps([tracker])
    assert "ruff format --check" in str(exc.value)


def test_validate_next_steps_requires_github_projects_reference(tmp_path: Path) -> None:
    tracker = _write_tracker(
        tmp_path, _baseline_content().replace("GitHub Projects", "roadmap")
    )
    with pytest.raises(ValueError) as exc:
        validate_next_steps([tracker])
    assert "GitHub Projects" in str(exc.value)


def _table_content() -> str:
    return """\
# Next Steps Tracker

| Priority | Status      | Area       | Summary                                                   | Notes |
| -------- | ----------- | ---------- | --------------------------------------------------------- | ----- |
| High     | Completed   | Governance | Frontier Elite quality gates (coverage ≥80, format, compile, validator) | UX + GitHub Projects automation wired via `python scripts/quality_gates.py` and `python scripts/verify_next_steps.py`. |
"""


def test_validate_next_steps_accepts_table_tracker(tmp_path: Path) -> None:
    table_path = tmp_path / "Next_Steps.md"
    table_path.write_text(_table_content(), encoding="utf-8")
    validate_next_steps([table_path])


def test_validate_next_steps_rejects_table_missing_keywords(tmp_path: Path) -> None:
    table_path = tmp_path / "Next_Steps.md"
    table_path.write_text(
        _table_content().replace("coverage ≥80", "coverage"), encoding="utf-8"
    )
    with pytest.raises(ValueError) as exc:
        validate_next_steps([table_path])
    assert "coverage ≥80" in str(exc.value)
