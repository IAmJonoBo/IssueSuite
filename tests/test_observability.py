from issuesuite.observability import configure_telemetry
from opentelemetry import trace


def test_configure_telemetry_sets_tracer_provider():
    configure_telemetry(service_name="issuesuite-test", exporter="console")
    tracer = trace.get_tracer("issuesuite-test")
    with tracer.start_as_current_span("demo") as span:
        assert span is not None
