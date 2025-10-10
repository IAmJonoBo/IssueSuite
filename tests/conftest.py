"""Pytest configuration for IssueSuite tests.

Ensures the in-repo `src` directory is on `sys.path` so the package can be
imported without an editable install (`pip install -e .`). This keeps CI and
local iteration fast and avoids polluting the environment when running tests
directly from a fresh clone.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# typing (PEP 585 built-in generics preferred)

_TEST_START_TIMES: dict[str, float] = {}
_TEST_DURATIONS: list[tuple[str, float]] = []

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    # Prepend so that 'python -m issuesuite.cli' finds local package first
    sys.path.insert(0, str(SRC))

# Force mock mode for the entire test session to avoid hanging on real GitHub CLI calls
os.environ.setdefault("ISSUES_SUITE_MOCK", "1")

# Ensure subprocesses (invoked by tests via `python -m issuesuite.cli`) can
# also import the in-repo package without requiring an editable install. We do
# this by injecting the src path into PYTHONPATH if it's not already present.
py_path = os.environ.get("PYTHONPATH", "")
parts = [p for p in py_path.split(os.pathsep) if p]
if str(SRC) not in parts:
    parts.insert(0, str(SRC))
    os.environ["PYTHONPATH"] = os.pathsep.join(parts)

# Ensure pytest-asyncio plugin is loaded explicitly so @pytest.mark.asyncio tests run
pytest_plugins = ["pytest_asyncio"]

# --- Timing utilities to help identify slow/stalling tests ---


def pytest_runtest_setup(item):  # type: ignore
    _TEST_START_TIMES[item.nodeid] = time.perf_counter()


def pytest_runtest_teardown(item):  # type: ignore
    start = _TEST_START_TIMES.pop(item.nodeid, None)
    if start is not None:
        duration = time.perf_counter() - start
        _TEST_DURATIONS.append((item.nodeid, duration))


def pytest_sessionfinish(session, exitstatus):  # type: ignore
    # Print a simple sorted timing table at the end to spot slow tests
    if not _TEST_DURATIONS:
        return
    slow = sorted(_TEST_DURATIONS, key=lambda x: x[1], reverse=True)[:10]
    print("\n=== Slowest Tests (top 10) ===")
    for nodeid, secs in slow:
        print(f"{secs:0.3f}s  {nodeid}")
    total_time = sum(d for _, d in _TEST_DURATIONS)
    print(
        f"Total recorded test time: {total_time:0.3f}s over {len(_TEST_DURATIONS)} tests"
    )
