"""Public helper to retrieve JSON Schemas used by IssueSuite.

This allows callers / AI agents to dynamically fetch schema definitions
without reading files or invoking the CLI.
"""
from __future__ import annotations
from typing import Dict, Any

def get_schemas() -> Dict[str, Any]:
    export_schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'title': 'IssueExport',
        'type': 'array',
        'items': {
            'type': 'object',
            'required': ['external_id','title','labels','hash','body'],
            'properties': {
                'external_id': {'type': 'string'},
                'title': {'type': 'string'},
                'labels': {'type': 'array','items':{'type':'string'}},
                'milestone': {'type': ['string','null']},
                'status': {'type': ['string','null']},
                'hash': {'type': 'string'},
                'body': {'type': 'string'},
            }
        }
    }
    summary_schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'title': 'IssueChangeSummary',
        'type': 'object',
        'required': ['schemaVersion','generated_at','dry_run','totals','changes'],
        'properties': {
            'schemaVersion': {'type':'integer'},
            'generated_at': {'type':'string'},
            'dry_run': {'type':'boolean'},
            'totals': {'type':'object'},
            'changes': {'type':'object'},
        }
    }
    return {'export': export_schema, 'summary': summary_schema}
