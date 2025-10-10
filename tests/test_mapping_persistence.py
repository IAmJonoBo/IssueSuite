from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

SAMPLE_ISSUES = textwrap.dedent(
    """\
## [slug: map-one]
```yaml
title: Map One
labels: [alpha]
milestone: "M1: Real-Time Foundation"
status: open
body: |
  Body One
```

## [slug: map-two]
```yaml
title: Map Two
labels: [beta]
milestone: "M2: Performance & Validation"
status: open
body: |
  Body Two
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


def _run(
    cmd: Sequence[str], cwd: Path, env: dict[str, str] | None = None
) -> tuple[int, str]:
    result = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, env=env, check=False
    )
    return int(result.returncode), str(result.stdout + result.stderr)


def test_mapping_persistence_mock_mode(tmp_path: Path) -> None:
    (tmp_path / "ISSUES.md").write_text(SAMPLE_ISSUES)
    (tmp_path / "issue_suite.config.yaml").write_text(MIN_CONFIG)
    env = os.environ.copy()
    env["ISSUES_SUITE_MOCK"] = "1"

    # First sync (non-dry-run so mapping persists)
    rc, out = _run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "sync",
            "--config",
            "issue_suite.config.yaml",
            "--update",
            "--summary-json",
            "issues_summary.json",
        ],
        tmp_path,
        env,
    )
    assert rc == 0, out
    summary_path = tmp_path / "issues_summary.json"
    summary_any: Any = json.loads(summary_path.read_text())
    assert isinstance(summary_any, dict)
    mapping_val = summary_any.get("mapping")
    mapping_raw = mapping_val if isinstance(mapping_val, dict) else {}
    mapping: dict[str, int] = {
        str(k): int(v)
        for k, v in mapping_raw.items()
        if isinstance(k, str) and isinstance(v, int)
    }
    assert mapping, "mapping should be present after first sync"
    index_file = tmp_path / ".issuesuite" / "index.json"
    assert index_file.exists(), "index.json should be written"
    stored_any: Any = json.loads(index_file.read_text())
    assert isinstance(stored_any, dict)
    stored_entries = (
        stored_any.get("entries") if isinstance(stored_any.get("entries"), dict) else {}
    )
    stored_map: dict[str, int] = {}
    for k, v in stored_entries.items():
        if isinstance(v, dict) and isinstance(v.get("issue"), int):
            stored_map[str(k)] = int(v["issue"])
    assert len(stored_map) == len(mapping)

    # Second sync should reuse mapping and potentially add none (no changes)
    rc2, out2 = _run(
        [
            sys.executable,
            "-m",
            "issuesuite.cli",
            "sync",
            "--config",
            "issue_suite.config.yaml",
            "--update",
            "--summary-json",
            "issues_summary.json",
        ],
        tmp_path,
        env,
    )
    assert rc2 == 0, out2
    summary2_any: Any = json.loads(summary_path.read_text())
    assert isinstance(summary2_any, dict)
    mapping2_val = summary2_any.get("mapping")
    mapping2_raw = mapping2_val if isinstance(mapping2_val, dict) else {}
    mapping2: dict[str, int] = {
        str(k): int(v)
        for k, v in mapping2_raw.items()
        if isinstance(k, str) and isinstance(v, int)
    }
    assert (
        mapping2 == mapping
    ), "mapping should remain stable across runs with no changes"
