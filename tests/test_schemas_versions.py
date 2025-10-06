from issuesuite import schemas
from issuesuite.schema_registry import get_schema_descriptor


def test_schemas_are_version_locked() -> None:
    loaded = schemas.get_schemas()
    summary_descriptor = get_schema_descriptor("summary")
    assert loaded["summary"]["$comment"].endswith(summary_descriptor.version)
    assert (
        loaded["summary"]["properties"]["schemaVersion"]["const"]
        == int(summary_descriptor.version)
    )


def test_ai_context_schema_version_matches_registry() -> None:
    loaded = schemas.get_schemas()
    descriptor = get_schema_descriptor("ai_context")
    assert loaded["ai_context"]["properties"]["schemaVersion"]["const"] == descriptor.version

