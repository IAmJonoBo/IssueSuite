from __future__ import annotations

import io
import logging
import sys
from typing import Any, Literal

trace: Any | None = None
TracerProvider: Any | None = None
BatchSpanProcessor: Any | None = None
ConsoleSpanExporter: Any | None = None
OTLPSpanExporter: Any | None = None
Resource: Any | None = None

try:  # pragma: no cover - optional dependency import guard
    from opentelemetry import trace as _trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as _OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource as _Resource
    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor as _BatchSpanProcessor,
    )
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter as _ConsoleSpanExporter,
    )
except Exception as exc:  # pragma: no cover - OpenTelemetry not available
    logging.getLogger(__name__).debug("OpenTelemetry import failed: %s", exc)
else:  # pragma: no cover - executed only when dependencies present
    trace = _trace
    TracerProvider = _TracerProvider
    BatchSpanProcessor = _BatchSpanProcessor
    ConsoleSpanExporter = _ConsoleSpanExporter
    OTLPSpanExporter = _OTLPSpanExporter
    Resource = _Resource

LOGGER = logging.getLogger(__name__)
_configured = False


class _ResilientConsoleWriter(io.TextIOBase):
    """Console writer that swallows ValueErrors triggered during interpreter shutdown."""

    def write(self, data: str) -> int:  # pragma: no cover - exercised via exporter callbacks
        try:
            return sys.stdout.write(data)
        except ValueError:
            LOGGER.debug("Console span exporter write suppressed; stream already closed")
            return len(data)

    def flush(self) -> None:  # pragma: no cover - exercised via exporter callbacks
        try:
            sys.stdout.flush()
        except ValueError:
            LOGGER.debug("Console span exporter flush suppressed; stream already closed")


def configure_telemetry(
    *,
    service_name: str,
    exporter: Literal["console", "otlp"] = "console",
    endpoint: str | None = None,
) -> None:
    """Configure OpenTelemetry tracing for IssueSuite if dependencies are present."""

    if _configured:
        return
    if (
        trace is None
        or TracerProvider is None
        or Resource is None
        or BatchSpanProcessor is None
        or ConsoleSpanExporter is None
    ):
        LOGGER.debug("OpenTelemetry SDK not available; telemetry disabled")
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if exporter == "otlp" and OTLPSpanExporter is not None:
        exporter_obj = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
    else:
        exporter_obj = ConsoleSpanExporter(out=_ResilientConsoleWriter())

    processor = BatchSpanProcessor(exporter_obj)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    globals()["_configured"] = True
    LOGGER.debug("OpenTelemetry tracing configured for %s via %s exporter", service_name, exporter)


def get_tracer(name: str) -> Any:  # pragma: no cover - thin wrapper
    if trace is None:
        raise RuntimeError("OpenTelemetry not configured")
    return trace.get_tracer(name)


__all__ = ["configure_telemetry", "get_tracer"]
