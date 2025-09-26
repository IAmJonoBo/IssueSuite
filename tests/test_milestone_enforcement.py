from __future__ import annotations

import os
import subprocess
from pathlib import Path


def write_basic_files(tmp_path: Path, issues_body: str) -> None:
    (tmp_path / "ISSUES.md").write_text(issues_body)
    (tmp_path / "issue_suite.config.yaml").write_text(
        """version: 1
source:
  file: ISSUES.md
  milestone_required: true
github:
  repo: null
"""
    )


def run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ISSUESUITE_AI_MODE"] = "1"
    return subprocess.run(
        ["python", "-m", "issuesuite", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_milestone_enforcement_failure(tmp_path: Path) -> None:
    # Missing milestone for slug -> should raise
    write_basic_files(
        tmp_path, "## [slug: alpha]\n\n```yaml\ntitle: Alpha\nlabels: [test]\n```\n"
    )
    proc = run_cli(tmp_path, "sync", "--config", "issue_suite.config.yaml", "--dry-run")
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "Milestone required" in proc.stderr or "Milestone required" in proc.stdout


def test_milestone_enforcement_success(tmp_path: Path) -> None:
    write_basic_files(
        tmp_path,
        '## [slug: alpha]\n\n```yaml\ntitle: Alpha\nmilestone: "Sprint 0: Mobilize & Baseline"\nlabels: [test]\n```\n',
    )
    proc = run_cli(tmp_path, "sync", "--config", "issue_suite.config.yaml", "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
