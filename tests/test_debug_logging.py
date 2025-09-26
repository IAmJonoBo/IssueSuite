from issuesuite import IssueSuite, load_config

CONFIG = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
"""

ISSUES = """## [slug: demo]
```yaml
title: Demo Issue
labels: [alpha]
status: open
body: |
  Body
```
"""


def test_debug_logging_emits(monkeypatch, tmp_path, capsys):
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(CONFIG)
    monkeypatch.setenv('ISSUESUITE_DEBUG', '1')
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    out = capsys.readouterr().out
    assert '[issuesuite] sync:start' in out
    assert '[issuesuite] sync:parsed 1 specs' in out
    assert '[issuesuite] sync:done' in out
