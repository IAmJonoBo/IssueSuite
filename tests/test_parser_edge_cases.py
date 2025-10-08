from pathlib import Path

import pytest

from issuesuite import IssueSuite

BASIC_CONFIG = """version: 1
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


def _write(tmp_path: Path, issues: str) -> IssueSuite:
    cfg = tmp_path / "issue_suite.config.yaml"
    cfg.write_text(BASIC_CONFIG)
    (tmp_path / "ISSUES.md").write_text(issues)
    return IssueSuite.from_config_path(cfg)


def test_missing_yaml_block(tmp_path: Path):
    suite = _write(tmp_path, "## [slug: bad-spec]\n\nNo fence here\n")
    with pytest.raises(ValueError, match="Missing ```yaml fenced block"):
        suite.parse()


def test_invalid_yaml(tmp_path: Path):
    suite = _write(tmp_path, "## [slug: bad-yaml]\n```yaml\n: - not valid\n```\n")
    with pytest.raises(ValueError, match="Invalid YAML"):
        suite.parse()


def test_missing_title(tmp_path: Path):
    suite = _write(tmp_path, "## [slug: no-title]\n```yaml\nlabels: [bug]\n```\n")
    with pytest.raises(ValueError, match="Missing title"):
        suite.parse()


def test_legacy_numeric_rejected(tmp_path: Path):
    suite = _write(tmp_path, "## 001 | Old Style\nlabels: bug\n---\nBody\n")
    with pytest.raises(ValueError, match="Legacy numeric issue format detected"):
        suite.parse()


def test_marker_insertion_idempotent(tmp_path: Path):
    issues = "## [slug: demo]\n```yaml\ntitle: Demo\nlabels: [x]\nbody: |\n  Line one\n```\n"
    suite = _write(tmp_path, issues)
    specs = suite.parse()
    assert "<!-- issuesuite:slug=demo -->" in specs[0].body
    # Parse again with marker already present
    (tmp_path / "ISSUES.md").write_text(
        "## [slug: demo]\n```yaml\ntitle: Demo\nlabels: [x]\nbody: |\n  <!-- issuesuite:slug=demo -->\n  Line one\n```\n"
    )
    specs2 = suite.parse()
    assert specs2[0].body.count("issuesuite:slug=demo") == 1
