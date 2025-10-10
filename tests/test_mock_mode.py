from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from issuesuite import IssueSuite, load_config

CFG = """\
version: 1
source:
  file: ISSUES.md
  milestone_required: false
defaults:
  inject_labels: []
  ensure_labels_enabled: true
  ensure_milestones_enabled: true
  ensure_milestones: ["M1"]
behavior: {}
ai: {}
"""

ISSUES = """## [slug: mock]
```yaml
title: Mock Issue
labels: [a, b]
status: open
body: |
  Body
```
"""


class Capture:  # test helper
    def __init__(self) -> None:
        self.calls: list[str] = []

    def record(self, command: str, *rest: str) -> str:  # simplified signature for lint happiness
        self.calls.append(command)
        return ""


def test_mock_mode_skips_all_gh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CFG)
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    capture = Capture()
    # If mock mode fails, these would be invoked; we intercept to ensure they are NOT called.
    monkeypatch.setattr(subprocess, "check_call", capture.record)
    monkeypatch.setattr(subprocess, "check_output", capture.record)

    suite.sync(dry_run=False, update=True, respect_status=False, preflight=True)
    out = capfd.readouterr().out
    # Expect mock create output (now prints full gh command), but no real gh calls captured via subprocess
    assert "MOCK" in out and "issue create" in out
    assert capture.calls == []
