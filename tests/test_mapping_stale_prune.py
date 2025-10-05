from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

SAMPLE_ISSUES_INITIAL = textwrap.dedent(
    """\
## [slug: keep-one]
```yaml
title: Keep One
labels: [x]
milestone: "M1: Alpha"
status: open
body: |
  Body A
```

## [slug: stale-two]
```yaml
title: Stale Two
labels: [y]
milestone: "M1: Alpha"
status: open
body: |
  Body B
```
"""
)

SAMPLE_ISSUES_AFTER = textwrap.dedent(
    """\
## [slug: keep-one]
```yaml
title: Keep One UPDATED
labels: [x]
milestone: "M1: Alpha"
status: open
body: |
  Body A Updated
```
"""
)

MIN_CONFIG = textwrap.dedent(
    """\nversion: 1\nsource:\n  file: ISSUES.md\n  id_pattern: "^[a-z0-9][a-z0-9-_]*$"\n  milestone_required: true\n  milestone_pattern: "^M[0-9]+:"\ndefaults:\n  inject_labels: []\n  ensure_labels_enabled: false\n  ensure_milestones_enabled: false\nbehavior:\n  truncate_body_diff: 50\nai:\n  schema_export_file: issue_export.schema.json\n  schema_summary_file: issue_change_summary.schema.json\n  schema_version: 1\n"""
)


def _run(cmd: Sequence[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env, check=False)
    return int(res.returncode), str(res.stdout + res.stderr)


def test_stale_mapping_pruned(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["ISSUES_SUITE_MOCK"] = "1"
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)

    # Initial issues with two slugs
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES_INITIAL)
    rc1, out1 = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'sync',
            '--config',
            'issue_suite.config.yaml',
            '--update',
            '--summary-json',
            'issues_summary.json',
        ],
        tmp_path,
        env,
    )
    assert rc1 == 0, out1

    idx = tmp_path / '.issuesuite' / 'index.json'
    assert idx.exists(), 'index.json missing after first sync'
    data_any: Any = json.loads(idx.read_text())
    entries = data_any.get('entries') if isinstance(data_any, dict) else {}
    entries_dict = cast(dict[Any, Any], entries if isinstance(entries, dict) else {})
    assert 'keep-one' in entries_dict and 'stale-two' in entries_dict

    # Modify ISSUES.md to remove stale-two
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES_AFTER)
    rc2, out2 = _run(
        [
            sys.executable,
            '-m',
            'issuesuite.cli',
            'sync',
            '--config',
            'issue_suite.config.yaml',
            '--update',
            '--summary-json',
            'issues_summary.json',
        ],
        tmp_path,
        env,
    )
    assert rc2 == 0, out2

    data_any2: Any = json.loads(idx.read_text())
    entries2 = data_any2.get('entries') if isinstance(data_any2, dict) else {}
    entries_dict2 = cast(dict[Any, Any], entries2 if isinstance(entries2, dict) else {})
    assert 'keep-one' in entries_dict2 and 'stale-two' not in entries_dict2, (
        'stale slug should be pruned'
    )
