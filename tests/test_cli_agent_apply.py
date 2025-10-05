import json
import os
import sys
import textwrap
import subprocess

SAMPLE_ISSUES = textwrap.dedent(
    """\
## [slug: done-item]
```yaml
title: Done item
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


def test_agent_apply_defaults_respect_status_and_dryrun(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    updates = {"updates": [{"slug": "done-item", "completed": True, "summary": "All done."}]}
    updates_path = tmp_path / "updates.json"
    updates_path.write_text(json.dumps(updates))

    env = os.environ.copy()
    env["ISSUES_SUITE_MOCK"] = "1"

    # Dry-run implied when --apply is not set
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
    assert rc == 0, out
    # Should indicate sync totals and not error
    assert "[agent-apply] sync totals" in out

    # Verify ISSUES.md updated: status set to closed and summary appended
    updated = (tmp_path / "ISSUES.md").read_text()
    assert "status: closed" in updated
    assert "### Completion summary (" in updated
    # Labels and milestone should be preserved
    assert "labels: [alpha]" in updated
    assert "milestone: M1" in updated

    # Now run with --apply and ensure not dry-run unless explicitly requested
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
            "--apply",
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    assert "[agent-apply] sync totals" in out

    # Explicit --dry-run-sync with --apply forces dry-run
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
            "--apply",
            "--dry-run-sync",
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    assert "[agent-apply] sync totals" in out

def test_agent_apply_requires_explicit_approval(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)
    updates_path = tmp_path / "updates.json"
    updates_path.write_text(
        json.dumps({"updates": [{"slug": "done-item", "completed": True}]})
    )

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
            "--require-approval",
        ],
        tmp_path,
        env,
    )
    assert rc == 3
    assert "approval required" in out


def test_agent_apply_accepts_updates_via_stdin(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    env = os.environ.copy()
    env["ISSUES_SUITE_MOCK"] = "1"

    updates = json.dumps({"updates": [{"slug": "done-item", "completed": True}]})
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--no-sync",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        input=updates,
        env=env,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "updated files" in combined


def test_agent_apply_rejects_invalid_json_input(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    env = os.environ.copy()
    env["ISSUES_SUITE_MOCK"] = "1"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "agent-apply",
            "--config",
            "issue_suite.config.yaml",
            "--no-sync",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        input="not-json",
        env=env,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "failed to read updates" in combined
