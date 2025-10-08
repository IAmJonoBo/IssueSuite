"""Public helper to retrieve JSON Schemas used by IssueSuite.

Schemas are intentionally shallow (top-level structure plus key required
properties) to give downstream tooling enough information for validation,
documentation, and AI reasoning without over‑specifying internals that may
change. Nested objects are left mostly open to allow additive evolution.
"""

from __future__ import annotations

from typing import Any

from .schema_registry import get_schema_descriptor

SCHEMA_KEY = "$schema"
SCHEMA_URL = "http://json-schema.org/draft-07/schema#"


def get_schemas() -> dict[str, Any]:
    """Return a mapping of schema name -> JSON Schema dictionary.

    Keys:
        export:    Schema describing the export artifact list.
        summary:   Schema describing the enriched sync summary (top-level keys).
        ai_context: Schema describing the AI context document (top-level keys).
    """
    export_descriptor = get_schema_descriptor("export")
    export_schema: dict[str, Any] = {
        SCHEMA_KEY: SCHEMA_URL,
        "$comment": f"IssueSuite export schema v{export_descriptor.version}",
        "title": "IssueExport",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["external_id", "title", "labels", "hash", "body"],
            "properties": {
                "external_id": {"type": "string"},
                "title": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "milestone": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "hash": {"type": "string"},
                "body": {"type": "string"},
            },
        },
    }

    summary_descriptor = get_schema_descriptor("summary")
    summary_schema: dict[str, Any] = {
        SCHEMA_KEY: SCHEMA_URL,
        "$comment": f"IssueSuite summary schema v{summary_descriptor.version}",
        "title": "IssueChangeSummary",
        "type": "object",
        "required": [
            "schemaVersion",
            "generated_at",
            "dry_run",
            "totals",
            "changes",
        ],
        "properties": {
            "schemaVersion": {
                "type": "string",
                "const": summary_descriptor.version,
            },
            "generated_at": {"type": "string"},
            "dry_run": {"type": "boolean"},
            "totals": {"type": "object"},
            "changes": {"type": "object"},
            "last_error": {
                "type": "object",
                "description": "Present only when sync failed",
                "properties": {
                    "category": {"type": "string"},
                    "transient": {"type": "boolean"},
                    "original_type": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    }

    ai_descriptor = get_schema_descriptor("ai_context")
    ai_context_schema: dict[str, Any] = {
        SCHEMA_KEY: SCHEMA_URL,
        "$comment": f"IssueSuite AI context schema v{ai_descriptor.version}",
        "title": "AIContext",
        "type": "object",
        "required": [
            "schemaVersion",
            "type",
            "spec_count",
            "preview",
            "mapping",
            "config",
            "env",
            "recommended",
        ],
        "properties": {
            "schemaVersion": {"type": "string", "const": ai_descriptor.version},
            "type": {"type": "string", "const": "issuesuite.ai-context"},
            "spec_count": {"type": "integer"},
            "preview": {"type": "array", "items": {"type": "object"}},
            "mapping": {"type": "object"},
            "config": {"type": "object"},
            "env": {"type": "object"},
            "project": {"type": "object"},
            "recommended": {"type": "object"},
        },
    }

    agent_descriptor = get_schema_descriptor("agent_updates")
    agent_update_schema: dict[str, Any] = {
        SCHEMA_KEY: SCHEMA_URL,
        "$comment": f"IssueSuite agent update schema v{agent_descriptor.version}",
        "title": "AgentUpdates",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["slug"],
            "properties": {
                "slug": {"type": "string", "minLength": 1},
                "external_id": {"type": "string", "minLength": 1},
                "title": {"type": "string"},
                "completed": {"type": "boolean"},
                "status": {"enum": ["open", "closed"]},
                "summary": {"type": "string"},
                "comment": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "milestone": {"type": "string"},
                "docs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["path"],
                        "properties": {
                            "path": {"type": "string"},
                            "append": {"type": "string"},
                            "replace": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            "anyOf": [
                {"required": ["slug"]},
                {"required": ["external_id"]},
            ],
            "additionalProperties": False,
        },
    }

    return {
        "export": export_schema,
        "summary": summary_schema,
        "ai_context": ai_context_schema,
        "agent_updates": agent_update_schema,
    }
