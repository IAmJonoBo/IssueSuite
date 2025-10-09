from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "ux_acceptance_report.json"
MAX_WIDTH = 100
COMMAND_MATRIX: tuple[tuple[str, ...], ...] = (
    (),
    ("sync",),
    ("security",),
    ("ai-context",),
    ("agent-apply",),
    ("upgrade",),
)
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _run_help(command: Sequence[str]) -> CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("ISSUES_SUITE_MOCK", "1")
    return run(
        [sys.executable, "-m", "issuesuite.cli", *command, "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@dataclass
class HelpCheck:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def lines(self) -> list[str]:
        return self.stdout.splitlines()

    @property
    def max_width(self) -> int:
        return max((len(line) for line in self.lines), default=0)

    @property
    def has_ansi(self) -> bool:
        return any(ANSI_PATTERN.search(line) for line in self.lines)

    @property
    def has_usage(self) -> bool:
        return any("usage" in line.lower() for line in self.lines)

    def to_summary(self) -> dict[str, Any]:
        return {
            "command": list(self.command) or ["<root>"],
            "returncode": self.returncode,
            "max_line_length": self.max_width,
            "has_ansi_sequences": self.has_ansi,
            "has_usage": self.has_usage,
            "status": self.status,
        }

    @property
    def status(self) -> str:
        if self.returncode != 0:
            return "fail"
        if self.max_width > MAX_WIDTH:
            return "fail"
        if self.has_ansi:
            return "fail"
        if not self.has_usage:
            return "fail"
        return "pass"


def run_checks(
    commands: Iterable[tuple[str, ...]] | None = None,
    *,
    runner: Callable[[Sequence[str]], CompletedProcess[str]] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    matrix = tuple(commands) if commands is not None else COMMAND_MATRIX
    exec_runner = runner or _run_help
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for command in matrix:
        result = exec_runner(command)
        check = HelpCheck(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        summary = check.to_summary()
        summaries.append(summary)
        if summary["status"] != "pass":
            failure_payload = dict(summary)
            failure_payload["stderr"] = result.stderr
            failures.append(failure_payload)
    report = {
        "max_width": MAX_WIDTH,
        "checks": summaries,
        "failures": failures,
        "passed": not failures,
    }
    report_path = output_path or REPORT_PATH
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_checks()
    if not report["passed"]:
        print("UX acceptance failures detected", file=sys.stderr)
        for failure in report["failures"]:
            command = " ".join(failure["command"])
            print(
                f" - {command or '<root>'}: width={failure['max_line_length']} returncode={failure['returncode']} ansi={failure['has_ansi_sequences']}",
                file=sys.stderr,
            )
        return 1
    print("UX acceptance checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
