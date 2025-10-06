"""Central registry for IssueSuite schema metadata.

The project emits several JSON artifacts (export, summary, AI context, and
agent updates).  Each artifact evolves independently, so keeping their version
metadata in a single place makes it easier to roll forward without drifting the
documentation or the CLI defaults.  Tests can also assert against this module to
guard future refactors.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaDescriptor:
    """Describes a JSON schema artifact shipped by IssueSuite."""

    name: str
    version: str
    description: str
    filename: str | None = None


_SCHEMA_REGISTRY: Mapping[str, SchemaDescriptor] = {
    "export": SchemaDescriptor(
        name="export",
        version="1",
        description="Schema describing the issues export artifact produced by `issuesuite export`.",
        filename="issue_export.schema.json",
    ),
    "summary": SchemaDescriptor(
        name="summary",
        version="2",
        description="Schema describing the enriched sync summary emitted via `issuesuite summary`.",
        filename="issue_change_summary.schema.json",
    ),
    "ai_context": SchemaDescriptor(
        name="ai_context",
        version="ai-context/1",
        description="Schema describing the AI context payload surfaced for agent integrations.",
        filename="ai_context.schema.json",
    ),
    "agent_updates": SchemaDescriptor(
        name="agent_updates",
        version="1",
        description="Schema describing the agent update ingestion payload for `issuesuite agent-apply`.",
    ),
}


def get_schema_descriptor(name: str) -> SchemaDescriptor:
    """Return the descriptor for a registered schema.

    Raises:
        KeyError: if the schema name is unknown.  Using ``KeyError`` keeps the
        function ergonomic for callers who want the usual mapping semantics
        while still producing a helpful error when assertions fail in tests.
    """

    return _SCHEMA_REGISTRY[name]


def get_schema_registry() -> Mapping[str, SchemaDescriptor]:
    """Expose the immutable registry for read-only introspection."""

    return _SCHEMA_REGISTRY


__all__ = ["SchemaDescriptor", "get_schema_descriptor", "get_schema_registry"]

