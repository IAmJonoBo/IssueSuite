from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_TARGET = SRC_ROOT / "issuesuite"
REPORT_PATH = PROJECT_ROOT / "type_coverage.json"
ERROR_FIELD_COUNT = 4


def _run_strict_mypy(targets: Sequence[str]) -> CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "mypy",
        "--strict",
        "--hide-error-context",
        "--no-error-summary",
        *targets,
    ]
    return run(command, capture_output=True, text=True, check=False)


def _collect_module_paths(roots: Iterable[Path]) -> set[str]:
    modules: set[str] = set()
    for root in roots:
        for path in root.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            modules.add(_normalize_path(path))
    return modules


def _normalize_path(path: Path | str) -> str:
    path_obj = Path(path)
    try:
        start = path_obj.parts.index("issuesuite")
        relevant = path_obj.parts[start:]
    except ValueError:  # pragma: no cover - defensive for non-package files
        relevant = path_obj.parts[-2:]
    return "/".join(relevant)


def _parse_error_counts(stdout: str, stderr: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for raw_line in [*stdout.splitlines(), *stderr.splitlines()]:
        if not raw_line or raw_line.startswith("Found "):
            continue
        parts = raw_line.split(":", 3)
        if len(parts) < ERROR_FIELD_COUNT:
            continue
        module_key = _normalize_path(parts[0])
        if "issuesuite" not in module_key:
            continue
        counts[module_key] += 1
    return counts


def generate_report(
    targets: Sequence[str] | None = None,
    *,
    runner: Callable[[Sequence[str]], CompletedProcess[str]] | None = None,
    module_roots: Iterable[Path] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    command_targets = [str(DEFAULT_TARGET)] if targets is None else list(targets)
    run_command = runner or _run_strict_mypy
    result = run_command(command_targets)
    modules = _collect_module_paths(module_roots or [DEFAULT_TARGET])
    error_counts = _parse_error_counts(result.stdout, result.stderr)
    module_reports: list[dict[str, Any]] = []
    strict_clean = 0
    for module in sorted(modules):
        errors = error_counts.get(module, 0)
        clean = errors == 0
        if clean:
            strict_clean += 1
        module_reports.append(
            {
                "module": module,
                "errors": errors,
                "strict_clean": clean,
            }
        )
    total_modules = len(modules) or 1
    payload = {
        "command": [sys.executable, "-m", "mypy", "--strict", *command_targets],
        "returncode": result.returncode,
        "modules_total": len(modules),
        "modules_strict_clean": strict_clean,
        "strict_ratio": strict_clean / total_modules,
        "modules": module_reports,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    report_path = output_path or REPORT_PATH
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    report = generate_report()
    summary = (
        f"Strict mypy clean modules: {report['modules_strict_clean']} / {report['modules_total']}"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
