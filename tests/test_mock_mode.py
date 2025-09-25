import os
import subprocess
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

ISSUES = """## 001 | Mock
labels: a,b
---
Body
"""


class Capture:
    def __init__(self):
        self.calls = []
    def __call__(self, *args, **kwargs):  # mimic subprocess funcs
        self.calls.append(args[0])
        return ''


def test_mock_mode_skips_all_gh(monkeypatch, tmp_path, capsys):
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    cfg_path.write_text(CFG)
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    capture = Capture()
    # If mock mode fails, these would be invoked; we intercept to ensure they are NOT called.
    monkeypatch.setattr(subprocess, 'check_call', capture)
    monkeypatch.setattr(subprocess, 'check_output', capture)

    suite.sync(dry_run=False, update=True, respect_status=False, preflight=True)
    out = capsys.readouterr().out
    # Expect mock create output, but no gh command captured
    assert 'MOCK create:' in out
    assert capture.calls == []