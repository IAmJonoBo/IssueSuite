from __future__ import annotations

from types import SimpleNamespace

import pytest

from issuesuite import observability


@pytest.fixture(autouse=True)
def reset_configured() -> None:
    observability._telemetry_configured["configured"] = False


def test_configure_telemetry_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observability, "_load_opentelemetry", lambda: None)
    events: dict[str, object] = {}

    monkeypatch.setattr(observability.trace, "TracerProvider", lambda: "provider")
    monkeypatch.setattr(
        observability.trace,
        "set_tracer_provider",
        lambda provider: events.update({"provider": provider}),
    )
    monkeypatch.setattr(
        observability.trace, "get_tracer", lambda name: events.update({"tracer": name})
    )

    observability.configure_telemetry(service_name="issuesuite")

    assert events["provider"] == "provider"
    assert events["tracer"] == "issuesuite"
    assert observability._telemetry_configured["configured"] is True


def test_configure_telemetry_with_otlp_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_calls: dict[str, object] = {}

    class DummyResource:
        @classmethod
        def create(cls, attrs: dict[str, str]) -> str:
            exporter_calls["resource"] = attrs
            return "resource"

    class DummyTracerProvider:
        def __init__(self, resource: str) -> None:
            exporter_calls["resource_arg"] = resource

        def add_span_processor(self, processor: object) -> None:
            exporter_calls["processor"] = processor

    class DummyBatchSpanProcessor:
        def __init__(self, exporter: object) -> None:
            exporter_calls["exporter"] = exporter

    class DummyConsoleExporter:
        def __call__(self) -> str:  # pragma: no cover - not exercised in OTLP branch
            return "console"

    class DummyOTLPExporter:
        def __init__(self, endpoint: str | None = None) -> None:
            exporter_calls["endpoint"] = endpoint

    dummy_trace = SimpleNamespace(
        set_tracer_provider=lambda provider: exporter_calls.update(
            {"provider": provider}
        ),
        get_tracer=lambda name: exporter_calls.update({"tracer": name}),
    )

    monkeypatch.setattr(
        observability,
        "_load_opentelemetry",
        lambda: {
            "trace": dummy_trace,
            "Resource": DummyResource,
            "TracerProvider": DummyTracerProvider,
            "BatchSpanProcessor": DummyBatchSpanProcessor,
            "ConsoleSpanExporter": DummyConsoleExporter,
            "OTLPSpanExporter": DummyOTLPExporter,
        },
    )

    observability.configure_telemetry(
        service_name="issuesuite", exporter="otlp", endpoint="https://otel"
    )

    assert exporter_calls["resource"] == {"service.name": "issuesuite"}
    assert exporter_calls["endpoint"] == "https://otel"
    assert exporter_calls["tracer"] == "issuesuite"
    assert observability._telemetry_configured["configured"] is True
