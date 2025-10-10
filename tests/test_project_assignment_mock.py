import os
from pathlib import Path

from issuesuite import IssueSuite  # type: ignore

CONFIG_YAML = """
version: 1
source:
    file: ISSUES.md
    id_pattern: "^[0-9]{3}$"
github:
    project:
        enable: true
        number: 1
defaults:
    ensure_labels_enabled: false
    ensure_milestones_enabled: false
behavior:
    truncate_body_diff: 50
"""

ISSUES_MD = """
## [slug: 001]
```yaml
title: One
labels: [demo]
status: open
body: |
    test body line
```
"""


def write_files(tmp_path: Path) -> None:  # noqa: D401
    (tmp_path / "issue_suite.config.yaml").write_text(CONFIG_YAML)
    (tmp_path / "ISSUES.md").write_text(ISSUES_MD)


def test_mock_project_assignment_mapping(tmp_path, monkeypatch):  # type: ignore
    # Force mock mode
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")
    write_files(tmp_path)
    os.chdir(tmp_path)
    suite = IssueSuite.from_config_path("issue_suite.config.yaml")
    summary = suite.sync(dry_run=False, update=True, respect_status=True, preflight=False)
    # Expect created and mapping for external id '001' -> synthetic int 1
    assert summary["totals"]["created"] == 1, summary
    assert summary["mapping"].get("001") == 1, summary


def test_dry_run_skips_assignment(tmp_path, monkeypatch):  # type: ignore
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")
    write_files(tmp_path)
    os.chdir(tmp_path)
    suite = IssueSuite.from_config_path("issue_suite.config.yaml")
    summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=False)
    # Created in dry-run but no mapping because assignment suppressed
    assert summary["totals"]["created"] == 1, summary
    assert summary["mapping"] == {}, summary
