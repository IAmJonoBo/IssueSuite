import json
import os
import subprocess
import sys
import textwrap

import pytest

from issuesuite.agent_updates import apply_agent_updates
from issuesuite.config import load_config

SAMPLE_ISSUES = textwrap.dedent(
    """\
## [slug: ready-item]
```yaml
title: Ready item
labels: [alpha]
milestone: M1
status: open
body: |
  Body here
```
"""
)

MIN_CONFIG = textwrap.dedent(
    """\
    version: 1
    source:
      file: ISSUES.md
      id_pattern: "^[a-z0-9][a-z0-9-_]*$"
      milestone_required: false
    defaults:
      inject_labels: []
      ensure_labels_enabled: false
      ensure_milestones_enabled: false
    behavior:
      truncate_body_diff: 50
    ai:
      schema_export_file: issue_export.schema.json
      schema_summary_file: issue_change_summary.schema.json
      schema_version: 1
    """
)


def _run(cmd, cwd, env=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, check=False)
    return result.returncode, result.stdout + result.stderr


def test_agent_apply_rejects_invalid_payload(tmp_path, monkeypatch):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    updates = {"updates": [{"summary": "missing slug"}]}
    updates_path = tmp_path / "updates.json"
    updates_path.write_text(json.dumps(updates))

    env = os.environ.copy()
    env["ISSUES_SUITE_MOCK"] = "1"

    rc, out = _run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--updates-json",
            str(updates_path),
        ],
        tmp_path,
        env,
    )

    assert rc != 0
    assert "validation" in out.lower()


def test_apply_agent_updates_missing_slug_rejected(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(MIN_CONFIG)

    cfg = load_config(cfg_path)

    with pytest.raises(ValueError) as excinfo:
        apply_agent_updates(cfg, {"updates": [{"summary": "missing slug"}]})

    assert "validation" in str(excinfo.value).lower()


def test_apply_agent_updates_validates_docs_entries(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(MIN_CONFIG)

    cfg = load_config(cfg_path)

    bad_doc_payload = {
        "updates": [
            {
                "slug": "ready-item",
                "docs": [
                    {"path": "", "append": 42},
                    "not-a-dict",
                ],
            }
        ]
    }

    with pytest.raises(ValueError) as excinfo:
        apply_agent_updates(cfg, bad_doc_payload)

    message = str(excinfo.value).lower()
    assert "validation" in message
    assert "docs" in message


def test_apply_agent_updates_appends_summary_and_docs(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(MIN_CONFIG)

    cfg = load_config(cfg_path)

    payload = {
        "updates": [
            {
                "slug": "ready-item",
                "completed": True,
                "summary": "Wrapped up work",
                "docs": [
                    {"path": "docs/notes.md", "append": "Extra context"},
                ],
            }
        ]
    }

    result = apply_agent_updates(cfg, payload)

    issues_text = (tmp_path / "ISSUES.md").read_text()
    doc_text = (tmp_path / "docs" / "notes.md").read_text()

    assert "status: closed" in issues_text
    assert "Completion summary" in issues_text
    assert "Wrapped up work" in issues_text
    assert "update-from: ready-item" in doc_text
    assert "Extra context" in doc_text
    assert sorted(result["changed_files"]) == [
        str(tmp_path / "ISSUES.md"),
        str(tmp_path / "docs" / "notes.md"),
    ]
