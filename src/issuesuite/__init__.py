"""IssueSuite - reusable declarative GitHub issue automation library.

High-level public API (stable):

from issuesuite import IssueSuite, load_config, IssueSpec

# Recommended: construct IssueSuite from config path
suite = IssueSuite.from_config_path('issue_suite.config.yaml')
summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=True)
print(summary['totals'])

# Alternatively, use load_config and pass to IssueSuite:
# cfg = load_config('issue_suite.config.yaml')
# suite = IssueSuite(cfg)

The CLI delegates to this library to allow installing via pip into other repositories.

Note:
- IssueSuite.from_config_path(config_path) is the preferred constructor for loading config and instantiating the suite in one step.
- See IssueSuite and load_config for additional options.
"""

from __future__ import annotations


from .ai_context import get_ai_context  # new public helper
from .config import SuiteConfig, load_config
from .core import IssueSpec, IssueSuite
from .scaffold import scaffold_project

# Explicitly import setup_wizard so it is present in the module
# from .setup_wizard import setup_wizard  # Removed due to missing module

# Version constant (sync manually with pyproject when extracted as standalone project)
__version__ = "0.1.13"


def __getattr__(name: str) -> object:
    """
    Lazy loading of select attributes to improve import performance.

    Lazily loaded attributes:
      - load_config
      - SuiteConfig
      - IssueSuite
      - IssueSpec
      - setup_wizard

    Other attributes (e.g., get_ai_context, scaffold_project, __version__) are eagerly loaded.
    """
    if name == "load_config":
        return load_config
    if name == "SuiteConfig":
        return SuiteConfig
    if name == "IssueSuite":
        return IssueSuite
    if name == "IssueSpec":
        return IssueSpec
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "load_config",
    "SuiteConfig",
    "IssueSuite",
    "IssueSpec",
    "get_ai_context",
    "scaffold_project",
    # "setup_wizard",  # Removed due to missing module
    "__version__",
]
