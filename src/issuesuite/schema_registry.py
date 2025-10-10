"""Central schema registry with version metadata and filenames."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaDescriptor:
    """Describes a schema artifact shipped with IssueSuite."""

    name: str
    version: str
    filename: str
    description: str


_REGISTRY: dict[str, SchemaDescriptor] = {
    "export": SchemaDescriptor(
        name="export",
        version="20250110",
        filename="issues_export.schema.json",
        description="Structured export of parsed issue specifications.",
    ),
    "summary": SchemaDescriptor(
        name="summary",
        version="20250110",
        filename="issue_change_summary.schema.json",
        description="Enriched sync summary emitted by orchestrator runs.",
    ),
    "ai_context": SchemaDescriptor(
        name="ai_context",
        version="ai-context/1",
        filename="ai_context.schema.json",
        description="AI context document consumed by assistants and tooling.",
    ),
    "agent_updates": SchemaDescriptor(
        name="agent_updates",
        version="20250110",
        filename="agent_updates.schema.json",
        description="Schema describing agent completion updates ingested via CLI.",
    ),
}


def _clone_descriptor(descriptor: SchemaDescriptor) -> SchemaDescriptor:
    return SchemaDescriptor(
        name=descriptor.name,
        version=descriptor.version,
        filename=descriptor.filename,
        description=descriptor.description,
    )


def get_schema_descriptor(name: str) -> SchemaDescriptor:
    """Return a defensive copy of a schema descriptor by name."""

    try:
        descriptor = _REGISTRY[name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown schema '{name}'") from exc
    return _clone_descriptor(descriptor)


def get_schema_registry() -> dict[str, SchemaDescriptor]:
    """Return a copy of the known schema descriptors keyed by name."""

    return {name: _clone_descriptor(descriptor) for name, descriptor in _REGISTRY.items()}


def iter_schema_descriptors() -> Iterable[SchemaDescriptor]:
    """Iterate over copies of registered schema descriptors."""

    for descriptor in _REGISTRY.values():
        yield _clone_descriptor(descriptor)


__all__ = [
    "SchemaDescriptor",
    "get_schema_descriptor",
    "get_schema_registry",
    "iter_schema_descriptors",
]
