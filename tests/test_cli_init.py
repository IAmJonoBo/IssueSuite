# ruff: noqa: ANN201, ANN001

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def _run(cmd: Sequence[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr


def test_cli_init_basic(tmp_path: Path) -> None:
    rc, out = _run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "init",
            "--directory",
            str(tmp_path),
        ],
        tmp_path,
    )
    assert rc == 0, out
    config_path = tmp_path / "issue_suite.config.yaml"
    issues_path = tmp_path / "ISSUES.md"
    assert config_path.exists()
    assert issues_path.exists()
    assert "[init] created issue_suite.config.yaml" in out
    assert "[init] created ISSUES.md" in out

    # Second run should not overwrite without --force
    rc, out = _run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "init",
            "--directory",
            str(tmp_path),
        ],
        tmp_path,
    )
    assert rc == 0, out
    assert "skipped" in out


def test_cli_init_with_extras(tmp_path: Path) -> None:
    rc, out = _run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "init",
            "--directory",
            str(tmp_path),
            "--include",
            "workflow",
            "--include",
            "gitignore",
            "--include",
            "vscode",
        ],
        tmp_path,
    )
    assert rc == 0, out
    assert (tmp_path / ".github" / "workflows" / "issuesuite-sync.yml").exists()
    assert (tmp_path / ".vscode" / "tasks.json").exists()
    gitignore = (tmp_path / ".gitignore").read_text()
    assert ".issuesuite/" in gitignore
