import pytest

from integrations.observability.otel import initialize_telemetry


def test_telemetry_is_optional_outside_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)

    providers = initialize_telemetry()
    assert providers.tracer is None
    assert providers.meter is None
    assert providers.api_request_counter is None
    providers.shutdown()


def test_production_requires_trace_and_metric_export_endpoints(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)

    with pytest.raises(RuntimeError, match="must be configured"):
        initialize_telemetry()
