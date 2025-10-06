from issuesuite.schema_registry import get_schema_descriptor, get_schema_registry


def test_schema_registry_contains_expected_entries() -> None:
    registry = get_schema_registry()
    assert {"export", "summary", "ai_context", "agent_updates"} <= set(registry)
    summary = registry["summary"]
    assert summary.version.isdigit()
    assert summary.filename == "issue_change_summary.schema.json"


def test_get_schema_descriptor_returns_deep_copy_like_behavior() -> None:
    descriptor = get_schema_descriptor("ai_context")
    assert descriptor.version.startswith("ai-context/")
    assert "AI context".lower() in descriptor.description.lower()

