import subprocess
from pathlib import Path
from issuesuite import IssueSuite, load_config
import yaml

CONFIG_TEMPLATE = """
version: 1
source:
  file: {issues_md}
  milestone_required: false
  auto_status_label: false
github: {{}}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: {ensure_labels}
  ensure_milestones_enabled: {ensure_milestones}
output: {{}}
behavior: {{}}
ai: {{}}
"""

ISSUES_MD_CONTENT = """## 001 | Test
labels: test-label
---
Body text
"""

def write_config(tmp_path, ensure_labels: bool, ensure_milestones: bool):
    issues_md = tmp_path / 'ISSUES.md'
    issues_md.write_text(ISSUES_MD_CONTENT)
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    cfg_path.write_text(CONFIG_TEMPLATE.format(issues_md=issues_md.name, ensure_labels=str(ensure_labels).lower(), ensure_milestones=str(ensure_milestones).lower()))
    return cfg_path

class CaptureCalls:
    def __init__(self):
        self.calls = []
    def __call__(self, *args, **kwargs):  # mimic subprocess functions
        self.calls.append(args[0])
        return ''


def test_preflight_disabled_no_calls(tmp_path, monkeypatch):
    cfg_path = write_config(tmp_path, ensure_labels=False, ensure_milestones=False)
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    capture = CaptureCalls()
    monkeypatch.setattr(subprocess, 'check_output', capture)
    monkeypatch.setattr(subprocess, 'check_call', capture)
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=True)
    assert capture.calls == []  # no gh invocations


def test_preflight_labels_enabled_invokes(monkeypatch, tmp_path):
    cfg_path = write_config(tmp_path, ensure_labels=True, ensure_milestones=False)
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    capture = CaptureCalls()
    monkeypatch.setattr(subprocess, 'check_output', capture)
    monkeypatch.setattr(subprocess, 'check_call', capture)
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=True)
    assert any('gh' in c for c in capture.calls)  # expect label list call at least
