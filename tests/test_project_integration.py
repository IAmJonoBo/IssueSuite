from issuesuite import IssueSuite, load_config

CONFIG_WITH_PROJECT = """
version: 1
source:
  file: ISSUES.md
github:
  project:
    enable: true
    number: 123
    field_mappings:
      labels: Status
      milestone: Priority
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: false
  level: INFO
"""

ISSUES = """## [slug: demo-issue]
```yaml
title: Demo Issue
labels: [bug, enhancement]
milestone: Sprint 1
body: |
  Body text for the issue
```
"""


def test_sync_with_project_assignment(monkeypatch, tmp_path):
    """Test sync process with project assignment enabled."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_PROJECT)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify project config is loaded correctly
    assert cfg.project_enable is True
    assert cfg.project_number == 123
    assert cfg.project_field_mappings == {"labels": "Status", "milestone": "Priority"}

    # Run sync to test project assignment integration
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)

    # Should complete without errors
    assert summary["totals"]["specs"] == 1
    assert summary["totals"]["created"] == 1


def test_sync_without_project_assignment(monkeypatch, tmp_path):
    """Test sync process with project assignment disabled."""
    cfg_content = CONFIG_WITH_PROJECT.replace("enable: true", "enable: false")

    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(ISSUES)
    cfg_path.write_text(cfg_content)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify project config is disabled
    assert cfg.project_enable is False

    # Run sync to ensure it still works when project assignment is disabled
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)

    # Should complete without errors
    assert summary["totals"]["specs"] == 1
    assert summary["totals"]["created"] == 1
