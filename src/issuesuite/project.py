"""Project integration groundwork (stub).

Defines minimal interfaces for future GitHub Project v2 support without adding
runtime dependencies today. This allows external tools / future versions to
introspect capabilities and conditionally enable project assignment.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, List, Protocol, Any

@dataclass
class ProjectConfig:
    enabled: bool
    number: Optional[int]
    field_mappings: Dict[str, str]

class ProjectAssigner(Protocol):  # pragma: no cover - interface only
    def assign(self, issue_number: int, spec: Any) -> None: ...  # noqa: D401

class NoopProjectAssigner:
    """Default assigner that performs no actions."""
    def assign(self, issue_number: int, spec: Any) -> None:  # pragma: no cover - trivial
        return


def build_project_assigner(cfg: ProjectConfig) -> ProjectAssigner:
    if not cfg.enabled:
        return NoopProjectAssigner()
    # Future: return real implementation (GraphQL / REST calls)
    return NoopProjectAssigner()
