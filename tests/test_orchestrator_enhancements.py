import json

import pytest

from issuesuite.config import load_config
from issuesuite.orchestrator import (
    _normalize_mapping,
    _prune_stale_entries,
    _truncate_body_diffs,
    sync_with_summary,
)

ERROR_PAYLOAD = {"code": "mock", "message": "boom"}


class DummySuite:
    def __init__(self, cfg):
        self.cfg = cfg
        self._last_error = ERROR_PAYLOAD

    def sync(self, **_: object):
        return {
            "totals": {
                "created": 1,
                "updated": 0,
                "closed": 0,
                "unchanged": 0,
                "parsed": 1,
            },
            "changes": {
                "updated": [
                    {
                        "external_id": "demo",
                        "diff": {"body_diff": ["a", "b", "c", "d"]},
                    }
                ]
            },
            "mapping": {"demo": 42},
        }


@pytest.fixture
def sample_config(tmp_path, monkeypatch):
    config_text = """
version: 1
source:
  file: ISSUES.md
output:
  summary_json: outputs/summaries/summary.json
  mapping_file: outputs/mapping/state.json
behavior:
  truncate_body_diff: 2
"""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(config_text)
    (tmp_path / "ISSUES.md").write_text("## [slug: demo]\n```yaml\ntitle: Demo\n```\n")
    cfg = load_config(cfg_path)
    monkeypatch.chdir(tmp_path)
    return cfg


def test_truncate_body_diffs_limits_entries():
    entry = {"diff": {"body_diff": ["alpha", "beta", "gamma"]}}
    summary = {"changes": {"updated": [entry]}}
    _truncate_body_diffs(summary, truncate=2)
    body_diff = summary["changes"]["updated"][0]["diff"]["body_diff"]
    assert body_diff == ["alpha", "beta", "... (truncated)"]


def test_normalize_mapping_filters_invalid_entries():
    raw = {"ok": {"issue": "101"}, "bad": {"issue": "abc"}, "other": "7"}
    normalized = _normalize_mapping(
        raw, context="test", value_getter=lambda v: v.get("issue")
    )
    assert normalized == {"ok": 101}


def test_prune_stale_entries_removes_missing_slugs():
    mapping = {"keep": 1, "drop": 2}
    _prune_stale_entries(mapping, {"keep"})
    assert mapping == {"keep": 1}


def test_sync_with_summary_creates_directories(sample_config, monkeypatch):
    monkeypatch.setattr("issuesuite.orchestrator.IssueSuite", DummySuite)
    base_dir = sample_config.source_file.parent
    mirror_path = base_dir / "mirror" / "index.json"
    monkeypatch.setenv("ISSUESUITE_INDEX_MIRROR", str(mirror_path))

    enriched = sync_with_summary(
        sample_config,
        dry_run=False,
        update=True,
        respect_status=True,
        preflight=False,
    )

    summary_path = base_dir / "outputs" / "summaries" / "summary.json"
    mapping_path = base_dir / "outputs" / "mapping" / "state.json"
    index_path = base_dir / ".issuesuite" / "index.json"

    assert summary_path.exists()
    data = json.loads(summary_path.read_text())
    assert data["mapping_snapshot"] == {"demo": 42}
    assert data["dry_run"] is False
    assert data["last_error"] == ERROR_PAYLOAD
    diff_entries = data["changes"]["updated"][0]["diff"]["body_diff"]
    assert diff_entries[-1] == "... (truncated)"

    assert mapping_path.exists()
    assert index_path.exists()
    assert mirror_path.exists()


def test_sync_with_summary_ai_mode_skips_persistence(sample_config, monkeypatch):
    monkeypatch.setattr("issuesuite.orchestrator.IssueSuite", DummySuite)
    monkeypatch.setenv("ISSUESUITE_AI_MODE", "1")
    base_dir = sample_config.source_file.parent
    mapping_path = base_dir / "outputs" / "mapping" / "state.json"

    enriched = sync_with_summary(
        sample_config,
        dry_run=False,
        update=True,
        respect_status=True,
        preflight=False,
    )

    assert enriched["dry_run"] is True
    assert not mapping_path.exists()
    assert "mapping_snapshot" not in enriched or enriched["mapping_snapshot"] == {
        "demo": 42
    }
