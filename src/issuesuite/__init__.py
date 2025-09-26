"""IssueSuite - reusable declarative GitHub issue automation library.

High-level public API (stable):

from issuesuite import IssueSuite, load_config, IssueSpec

suite = IssueSuite.from_config_path('issue_suite.config.yaml')
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=True)
print(summary['totals'])

The CLI delegates to this library to allow installing via pip into other repositories.
"""

from __future__ import annotations

from .ai_context import get_ai_context  # new public helper
from .config import SuiteConfig, load_config
from .core import IssueSpec, IssueSuite

# Version constant (sync manually with pyproject when extracted as standalone project)
__version__ = "0.1.8"

def __getattr__(name: str) -> object:
    """Lazy loading of modules to improve import performance."""
    if name == "load_config":
        return load_config
    elif name == "SuiteConfig":
        return SuiteConfig
    elif name == "IssueSuite":
        return IssueSuite
    elif name == "IssueSpec":
        return IssueSpec
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "load_config",
    "SuiteConfig",
    "IssueSuite",
    "IssueSpec",
    "get_ai_context",
    "__version__",
]
