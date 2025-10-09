from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FILES: tuple[Path, ...] = (
    Path("Next Steps.md"),
    Path("Next_Steps.md"),
)

REQUIRED_SECTIONS: tuple[str, ...] = (
    "## Tasks",
    "## Steps",
    "## Deliverables",
    "## Quality Gates",
    "## Links",
    "## Risks / Notes",
)

REQUIRED_QUALITY_KEYWORDS: tuple[str, ...] = (
    "coverage ≥80",
    "pytest --cov=issuesuite --cov-report=term --cov-report=xml",
    "ruff check",
    "ruff format --check",
    "mypy src",
    "python -m bandit -r src",
    "python -m detect_secrets scan --baseline .secrets.baseline",
    "python -m pip_audit --progress-spinner off --strict",
    "python -m issuesuite.dependency_audit",
    "python -m compileall src",
    "python scripts/generate_performance_report.py",
    "python -m issuesuite.benchmarking --check",
    "python -m issuesuite.advisory_refresh --check",
    "python -m build",
    "python scripts/quality_gates.py",
    "python scripts/verify_next_steps.py",
)

PROJECT_MANAGEMENT_KEYWORDS: tuple[str, ...] = (
    "github project",
    "github projects",
)

UX_KEYWORDS: tuple[str, ...] = (
    "ux",
    "user experience",
)


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def _extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    tail = text.find("\n## ", start)
    if tail == -1:
        return text[start:]
    return text[start:tail]


def _ensure_keywords(section: str, keywords: Iterable[str]) -> list[str]:
    normalized = section.lower()
    missing: list[str] = []
    for keyword in keywords:
        if keyword.lower() not in normalized:
            missing.append(keyword)
    return missing


def _select_default_paths() -> list[Path]:
    selected = [path for path in DEFAULT_FILES if path.exists()]
    if not selected:
        raise ValueError("No Next Steps files found in repository root.")
    return selected


def _validate_table_tracker(path: Path, text: str) -> list[ValidationIssue]:
    normalized = text.lower()
    requirements = [
        "coverage ≥80",
        "python scripts/quality_gates.py",
        "python scripts/verify_next_steps.py",
    ]
    issues: list[ValidationIssue] = []
    for requirement in requirements:
        if requirement not in normalized:
            issues.append(
                ValidationIssue(
                    path,
                    f"table tracker missing reference to '{requirement}'",
                )
            )
    if not any(keyword in normalized for keyword in PROJECT_MANAGEMENT_KEYWORDS):
        issues.append(
            ValidationIssue(
                path,
                "table tracker must mention GitHub Projects integration",
            )
        )
    if not any(keyword in normalized for keyword in UX_KEYWORDS):
        issues.append(
            ValidationIssue(path, "table tracker must reference UX expectations"),
        )
    return issues


def _validate_markdown_tracker(path: Path, text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(ValidationIssue(path, f"missing section: {section}"))
    quality_section = _extract_section(text, "Quality Gates")
    if not quality_section.strip():
        issues.append(ValidationIssue(path, "missing Quality Gates details"))
    else:
        missing_keywords = _ensure_keywords(quality_section, REQUIRED_QUALITY_KEYWORDS)
        for keyword in missing_keywords:
            issues.append(
                ValidationIssue(
                    path,
                    f"Quality Gates section missing reference to '{keyword}'",
                )
            )
    normalized = text.lower()
    if not any(keyword in normalized for keyword in PROJECT_MANAGEMENT_KEYWORDS):
        issues.append(
            ValidationIssue(
                path,
                "project management guidance must mention GitHub Projects integration",
            )
        )
    if not any(keyword in normalized for keyword in UX_KEYWORDS):
        issues.append(
            ValidationIssue(path, "UX excellence criteria must be documented"),
        )
    return issues


def validate_next_steps(paths: Sequence[Path] | None = None) -> None:
    candidates = list(paths) if paths else _select_default_paths()
    issues: list[ValidationIssue] = []
    for path in candidates:
        if not path.exists():
            issues.append(ValidationIssue(path, "file does not exist"))
            continue
        text = path.read_text(encoding="utf-8")
        if text.lstrip().startswith("# Next Steps Tracker"):
            issues.extend(_validate_table_tracker(path, text))
            continue
        issues.extend(_validate_markdown_tracker(path, text))
    if issues:
        formatted = "\n".join(issue.format() for issue in issues)
        raise ValueError(f"Next Steps validation failed:\n{formatted}")


__all__ = ["validate_next_steps", "ValidationIssue", "DEFAULT_FILES"]
