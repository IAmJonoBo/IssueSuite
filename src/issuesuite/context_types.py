from __future__ import annotations

from typing import Any, TypedDict

# Typed structures for AI context output


class AIContextMapping(TypedDict, total=False):
    present: bool
    size: int
    snapshot_included: bool
    # Optional when present, contains snapshot sizes by section; None if omitted
    snapshot: dict[str, int] | None


class AIContextConfig(TypedDict):
    dry_run_default: bool
    ensure_labels_enabled: bool
    ensure_milestones_enabled: bool
    truncate_body_diff: int
    concurrency_enabled: bool
    concurrency_max_workers: int
    performance_benchmarking: bool


class AIContextEnv(TypedDict):
    ai_mode: bool
    mock_mode: bool
    debug_logging: bool


class AIContextProject(TypedDict, total=False):
    enabled: bool
    number: int | None
    field_mappings: dict[str, str]
    has_mappings: bool


class AIContextRecommended(TypedDict):
    safe_sync: str
    export: str
    summary: str
    usage: list[str]
    env: list[str]


class AIContextErrorsRetry(TypedDict):
    attempts_env: str
    base_env: str
    strategy: str


class AIContextErrors(TypedDict):
    categories: list[str]
    retry: AIContextErrorsRetry


class AIContextDoc(TypedDict):
    schemaVersion: str
    type: str
    spec_count: int
    preview: list[dict[str, Any]]
    errors: AIContextErrors
    mapping: AIContextMapping
    config: AIContextConfig
    env: AIContextEnv
    project: AIContextProject
    recommended: AIContextRecommended


__all__ = [
    "AIContextMapping",
    "AIContextConfig",
    "AIContextEnv",
    "AIContextProject",
    "AIContextRecommended",
    "AIContextErrorsRetry",
    "AIContextErrors",
    "AIContextDoc",
]
