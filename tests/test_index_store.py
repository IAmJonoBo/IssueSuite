import json

from issuesuite.index_store import IndexDocument, load_index_document, persist_index_document


def test_index_persistence_round_trip(tmp_path):
    path = tmp_path / "index.json"
    doc = IndexDocument(entries={"alpha": {"issue": 7, "hash": "abc"}}, repo="acme/widgets")
    persist_index_document(path, doc)

    loaded = load_index_document(path)
    assert loaded.entries == doc.entries
    assert loaded.signature

    raw = json.loads(path.read_text())
    assert raw["signature"] == loaded.signature
    assert raw["version"] == doc.version


def test_index_signature_mismatch_returns_empty(tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps({
        "version": 1,
        "generated_at": "2024-01-01T00:00:00Z",
        "signature": "deadbeef",
        "entries": {"alpha": {"issue": 1, "hash": "zzz"}},
    }))

    loaded = load_index_document(path)
    assert loaded.entries == {}
