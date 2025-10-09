"""IssueSuite runtime customizations for local CLI usage.

This module is imported automatically by Python when it exists on the import
path. We use the hook to stabilise ``python -m pip_audit`` executions so that
hermetic runners inherit the same resilient behaviour exposed via
``issuesuite.cli security``. The patch installs the offline-aware
``ResilientPyPIService`` shim and applies a conservative timeout so
``pip-audit --strict`` can't hang indefinitely when the network is unreachable.

Set ``ISSUESUITE_DISABLE_PIP_AUDIT_SITE_PATCH=1`` to opt out (for example, when
packaging IssueSuite as a library and deferring to the upstream pip-audit
behaviour).
"""

from __future__ import annotations

import atexit
import os
from collections.abc import Iterable
from importlib import import_module


def _load_advisories() -> Iterable[object]:
    """Load the curated advisory dataset if available."""

    try:  # Late import so bare Python invocations don't require package deps
        dependency_audit = import_module("issuesuite.dependency_audit")
    except Exception:  # pragma: no cover - optional dependency missing
        return ()
    try:
        return tuple(dependency_audit.load_advisories())
    except Exception:  # pragma: no cover - corrupted dataset surfaces gracefully
        return ()


def _install_resilient_service(advisories: Iterable[object]) -> bool:
    """Install the resilient pip-audit service shim if the dependency exists."""

    try:
        integration = import_module("issuesuite.pip_audit_integration")
    except Exception:  # pragma: no cover - pip-audit not installed
        return False

    try:
        installer = integration.install_resilient_pip_audit
    except AttributeError:  # pragma: no cover - unexpected integration shape
        return False

    restore = installer(advisories=advisories)

    def _cleanup() -> None:  # pragma: no cover - defensive cleanup
        try:
            restore()
        except Exception:
            pass

    atexit.register(_cleanup)
    return True


def _patch_pip_audit() -> bool:
    """Patch pip-audit so module execution mirrors the IssueSuite CLI guardrails."""

    if os.environ.get("ISSUESUITE_DISABLE_PIP_AUDIT_SITE_PATCH") == "1":
        return False

    advisories = _load_advisories()
    patched = _install_resilient_service(advisories)
    if not patched:
        return False

    # Ensure upstream pip-audit respects a sensible timeout in hermetic runs.
    os.environ.setdefault("PIP_AUDIT_TIMEOUT", "60")
    # Disable the spinner by default to reduce noisy CI logs.
    os.environ.setdefault("PIP_AUDIT_PROGRESS", "off")
    return True


_PATCH_APPLIED = _patch_pip_audit()

__all__ = ["_patch_pip_audit", "_PATCH_APPLIED"]
