import json
import os
import subprocess
import sys
import textwrap

SAMPLE_ISSUES = textwrap.dedent(
    """\
## [slug: cli-alpha]
```yaml
title: CLI Alpha
labels: [alpha, beta]
milestone: "M1: Real-Time Foundation"
status: open
body: |
  Body A line
```

## [slug: cli-beta]
```yaml
title: CLI Beta
labels: [gamma, "status:closed"]
milestone: "M2: Performance & Validation"
status: closed
body: |
  Body B line
```
"""
)

MIN_CONFIG = textwrap.dedent(
    """\
    version: 1
    source:
      file: ISSUES.md
      id_pattern: "^[a-z0-9][a-z0-9-_]*$"
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

EXPECTED_SPEC_COUNT = 2


def _run(cmd, cwd, env=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, check=False)
    return result.returncode, result.stdout + result.stderr


def test_cli_summary_export_schema_validate_sync(tmp_path):
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    env = os.environ.copy()
    env['ISSUES_SUITE_MOCK'] = '1'

    # summary
    rc, out = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'summary',
            '--config',
            'issue_suite.config.yaml',
            '--limit',
            '5',
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    assert 'Total: 2' in out

    # export
    export_path = tmp_path / 'out.json'
    rc, out = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'export',
            '--config',
            'issue_suite.config.yaml',
            '--output',
            str(export_path),
            '--pretty',
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    data = json.loads(export_path.read_text())
    assert len(data) == EXPECTED_SPEC_COUNT
    assert {d['external_id'] for d in data} == {'cli-alpha', 'cli-beta'}

    # schema (stdout)
    rc, out = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'schema',
            '--config',
            'issue_suite.config.yaml',
            '--stdout',
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    schemas = json.loads(out)
    # Now includes ai_context and agent update schemas as well
    assert set(schemas.keys()) == {'export', 'summary', 'ai_context', 'agent_updates'}

    # validate
    rc, out = _run(
        [sys.executable, '-m', 'issuesuite.cli', 'validate', '--config', 'issue_suite.config.yaml'],
        tmp_path,
        env,
    )
    assert rc == 0, out

    # sync (dry-run) with summary output
    summary_path = tmp_path / 'summary.json'
    rc, out = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'sync',
            '--config',
            'issue_suite.config.yaml',
            '--dry-run',
            '--update',
            '--summary-json',
            str(summary_path),
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    summary = json.loads(summary_path.read_text())
    assert summary['totals']['specs'] == EXPECTED_SPEC_COUNT
    assert len(summary['changes']['created']) == EXPECTED_SPEC_COUNT


def test_marker_and_prune(tmp_path):
    issues_file = tmp_path / 'ISSUES.md'
    issues_file.write_text(SAMPLE_ISSUES)
    (tmp_path / 'issue_suite.config.yaml').write_text(MIN_CONFIG)
    env = os.environ.copy()
    env['ISSUES_SUITE_MOCK'] = '1'
    # First sync (non dry-run) to create issues and persist mapping
    rc, out = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'sync',
            '--config',
            'issue_suite.config.yaml',
            '--update',
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    # Body marker should have been inserted (check in mock create output)
    assert '<!-- issuesuite:slug=cli-alpha -->' in out
    # Remove one spec and prune
    pruned_content = SAMPLE_ISSUES.split('\n\n## [slug: cli-beta]')[0] + '\n'
    issues_file.write_text(pruned_content)
    rc, out2 = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'sync',
            '--config',
            'issue_suite.config.yaml',
            '--update',
            '--prune',
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out2
