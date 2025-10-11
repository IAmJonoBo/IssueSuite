from types import SimpleNamespace

from issuesuite.index_store import IndexDocument
from issuesuite import mapping_utils


def test_load_mapping_snapshot_converts_and_skips_invalid(monkeypatch, tmp_path):
    cfg = SimpleNamespace(source_file=tmp_path / "ISSUES.md")
    document = IndexDocument(
        entries={
            "alpha": {"issue": "101"},
            "bravo": {"issue": 202},
            "charlie": {"issue": "not-a-number"},
            "delta": {"other": "ignored"},
        }
    )

    def fake_loader(path):
        expected = cfg.source_file.parent / ".issuesuite" / "index.json"
        assert path == expected
        return document

    monkeypatch.setattr(mapping_utils, "load_index_document", fake_loader)

    snapshot = mapping_utils.load_mapping_snapshot(cfg)

    assert snapshot == {"alpha": 101, "bravo": 202}
