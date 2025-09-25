import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path


SAMPLE_ISSUES = textwrap.dedent(
    """\
    ## 100 | CLI Alpha
    labels: alpha,beta
    milestone: M1: Real-Time Foundation
    status: open
    ---
    Body A line

    ## 101 | CLI Beta
    labels: gamma,status:closed
    milestone: M2: Performance & Validation
    status: closed
    ---
    Body B line
    """
)

MIN_CONFIG = textwrap.dedent(
    """\
    version: 1
    source:
      file: ISSUES.md
      id_pattern: "^[0-9]{3}$"
      milestone_required: true
      milestone_pattern: "^M[0-9]+:"
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
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    return result.returncode, result.stdout + result.stderr


def test_cli_summary_export_schema_validate_sync(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    env = os.environ.copy()
    env['ISSUES_SUITE_MOCK'] = '1'

    # summary
    rc, out = _run([sys.executable, '-m', 'issuesuite.cli', 'summary', '--config', 'issue_suite.config.yaml', '--limit', '5'], tmp_path, env)
    assert rc == 0, out
    assert 'Total: 2' in out

    # export
    export_path = tmp_path / 'out.json'
    rc, out = _run([sys.executable, '-m', 'issuesuite.cli', 'export', '--config', 'issue_suite.config.yaml', '--output', str(export_path), '--pretty'], tmp_path, env)
    assert rc == 0, out
    data = json.loads(export_path.read_text())
    assert len(data) == 2
    assert {d['external_id'] for d in data} == {'100', '101'}

    # schema (stdout)
    rc, out = _run([sys.executable, '-m', 'issuesuite.cli', 'schema', '--config', 'issue_suite.config.yaml', '--stdout'], tmp_path, env)
    assert rc == 0, out
    schemas = json.loads(out)
    assert set(schemas.keys()) == {'export', 'summary'}

    # validate
    rc, out = _run([sys.executable, '-m', 'issuesuite.cli', 'validate', '--config', 'issue_suite.config.yaml'], tmp_path, env)
    assert rc == 0, out

    # sync (dry-run) with summary output
    summary_path = tmp_path / 'summary.json'
    rc, out = _run([
        sys.executable, '-m', 'issuesuite.cli', 'sync', '--config', 'issue_suite.config.yaml', '--dry-run', '--update', '--summary-json', str(summary_path)
    ], tmp_path, env)
    assert rc == 0, out
    summary = json.loads(summary_path.read_text())
    assert summary['totals']['specs'] == 2
    assert len(summary['changes']['created']) == 2
