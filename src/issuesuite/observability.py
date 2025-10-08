"""Lightweight helpers for configuring OpenTelemetry exporters."""

from __future__ import annotations

import importlib
import logging
from functools import lru_cache
from typing import Any, Final

from opentelemetry import trace

_telemetry_configured: Final[dict[str, bool]] = {"configured": False}


@lru_cache(maxsize=1)
def _load_opentelemetry() -> dict[str, Any] | None:
    try:  # pragma: no cover - optional dependency
        trace_module = importlib.import_module("opentelemetry.trace")
        exporter_module = importlib.import_module(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter"
        )
        resources_module = importlib.import_module("opentelemetry.sdk.resources")
        trace_sdk_module = importlib.import_module("opentelemetry.sdk.trace")
        export_module = importlib.import_module("opentelemetry.sdk.trace.export")
    except ImportError:
        return None

    return {
        "trace": trace_module,
        "TracerProvider": trace_sdk_module.TracerProvider,
        "Resource": resources_module.Resource,
        "BatchSpanProcessor": export_module.BatchSpanProcessor,
        "ConsoleSpanExporter": export_module.ConsoleSpanExporter,
        "OTLPSpanExporter": exporter_module.OTLPSpanExporter,
    }


def configure_telemetry(
    *,
    service_name: str,
    exporter: str = "console",
    endpoint: str | None = None,
) -> None:
    """Configure OpenTelemetry once for the CLI process."""

    if _telemetry_configured["configured"]:
        return

    runtime = _load_opentelemetry()
    if runtime is None:
        logging.getLogger(__name__).debug(
            "OpenTelemetry packages not installed; falling back to shim"
        )
        provider = trace.TracerProvider()
        trace.set_tracer_provider(provider)
        trace.get_tracer(service_name)
        _telemetry_configured["configured"] = True
        return

    resource_cls = runtime["Resource"]
    tracer_provider_cls = runtime["TracerProvider"]
    batch_span_processor_cls = runtime["BatchSpanProcessor"]
    console_span_exporter_cls = runtime["ConsoleSpanExporter"]

    resource = resource_cls.create({"service.name": service_name})
    provider = tracer_provider_cls(resource=resource)

    if exporter.lower() == "otlp":
        otlp_cls = runtime["OTLPSpanExporter"]
        span_exporter = otlp_cls(endpoint=endpoint) if endpoint else otlp_cls()
    else:
        span_exporter = console_span_exporter_cls()

    provider.add_span_processor(batch_span_processor_cls(span_exporter))
    runtime["trace"].set_tracer_provider(provider)
    runtime["trace"].get_tracer(service_name)
    _telemetry_configured["configured"] = True


__all__ = ["configure_telemetry"]
