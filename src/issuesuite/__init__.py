"""IssueSuite - reusable declarative GitHub issue automation library.

High-level public API (stable):

from issuesuite import IssueSuite, load_config, IssueSpec

suite = IssueSuite.from_config_path('issue_suite.config.yaml')
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=True)
print(summary['totals'])

The CLI delegates to this library to allow installing via pip into other repositories.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING or sys.version_info >= (3, 10):
    from .config import SuiteConfig, load_config
    from .core import IssueSpec, IssueSuite

# Version constant (sync manually with pyproject when extracted as standalone project)
__version__ = '0.1.4'


def __getattr__(name: str):
    """Lazy loading of modules to improve import performance."""
    if name == 'load_config':
        from .config import load_config
        return load_config
    elif name == 'SuiteConfig':
        from .config import SuiteConfig
        return SuiteConfig
    elif name == 'IssueSuite':
        from .core import IssueSuite
        return IssueSuite
    elif name == 'IssueSpec':
        from .core import IssueSpec
        return IssueSpec
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    'load_config',
    'SuiteConfig',
    'IssueSuite',
    'IssueSpec',
    '__version__',
]
