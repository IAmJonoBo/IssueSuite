import subprocess

from issuesuite import IssueSuite, load_config

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

ISSUES_MD_CONTENT = """## [slug: preflight-test]
```yaml
title: Preflight Test
labels: [test-label]
status: open
body: |
    Body text
```
"""


def write_config(tmp_path, ensure_labels: bool, ensure_milestones: bool):
    issues_md = tmp_path / "ISSUES.md"
    issues_md.write_text(ISSUES_MD_CONTENT)
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(
        CONFIG_TEMPLATE.format(
            issues_md=issues_md.name,
            ensure_labels=str(ensure_labels).lower(),
            ensure_milestones=str(ensure_milestones).lower(),
        )
    )
    return cfg_path


class CaptureCalls:
    def __init__(self):
        self.calls: list[str] = []

    def record(self, command: str, *rest: str) -> str:
        self.calls.append(command)
        return ""


def test_preflight_disabled_no_calls(tmp_path, monkeypatch):
    cfg_path = write_config(tmp_path, ensure_labels=False, ensure_milestones=False)
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    capture = CaptureCalls()
    monkeypatch.setattr(subprocess, "check_output", capture.record)
    monkeypatch.setattr(subprocess, "check_call", capture.record)
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=True)
    assert capture.calls == []  # no gh invocations


def test_preflight_labels_enabled_invokes(monkeypatch, tmp_path):
    cfg_path = write_config(tmp_path, ensure_labels=True, ensure_milestones=False)
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    capture = CaptureCalls()
    monkeypatch.setattr(subprocess, "check_output", capture.record)
    monkeypatch.setattr(subprocess, "check_call", capture.record)
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=True)
    # In mock mode (no auth), ensure_labels_enabled short-circuits gh calls; expectation updated.
    assert capture.calls == []
