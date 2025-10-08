"""Lightweight OpenTelemetry shim used for tests.

The real `opentelemetry` package is an optional dependency of IssueSuite. For the
integration tests in this repository we only need a tiny subset of the API to
exist so this shim provides the necessary hooks:

* ``opentelemetry.trace`` module with a tracer provider, tracer factory, and
  spans supporting ``set_attribute``.
* Functions to get and set the global tracer provider mirroring the official
  API surface.

If the real package is installed it will shadow this shim on ``PYTHONPATH``.
"""

from __future__ import annotations

from . import trace

__all__ = ["trace"]
