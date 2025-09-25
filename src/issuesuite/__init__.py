"""IssueSuite - reusable declarative GitHub issue automation library.

High-level public API (stable):

from issuesuite import IssueSuite, load_config, IssueSpec

suite = IssueSuite.from_config_path('issue_suite.config.yaml')
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=True)
print(summary['totals'])

The CLI (scripts/issue_suite.py) can later delegate to this library to allow
installing via pip into other repositories.
"""
from __future__ import annotations

from .config import load_config, SuiteConfig
from .core import IssueSuite, IssueSpec  # re-export

# Version constant (sync manually with pyproject when extracted as standalone project)
__version__ = '0.1.4'

__all__ = [
    'load_config',
    'SuiteConfig',
    'IssueSuite',
    'IssueSpec',
    '__version__',
]
