"""OpenTelemetry SDK setup for control-plane request traces and metrics."""

import os
from dataclasses import dataclass

from opentelemetry import metrics, trace
from opentelemetry.metrics import Counter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


@dataclass
class TelemetryProviders:
    tracer: TracerProvider | None
    meter: MeterProvider | None
    api_request_counter: Counter | None

    def shutdown(self) -> None:
        if self.tracer is not None:
            self.tracer.shutdown()
        if self.meter is not None:
            self.meter.shutdown()


def initialize_telemetry() -> TelemetryProviders:
    traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    production = os.getenv("ENVIRONMENT", "").strip().lower() in {"production", "staging"}
    if production and (not traces_endpoint or not metrics_endpoint):
        raise RuntimeError(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT and OTEL_EXPORTER_OTLP_METRICS_ENDPOINT "
            "must be configured in production"
        )

    resource = Resource.create({"service.name": "ai-governance-control-api"})
    tracer_provider = None
    meter_provider = None
    request_counter = None
    if traces_endpoint:
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint))
        )
        trace.set_tracer_provider(tracer_provider)
    if metrics_endpoint:
        reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=metrics_endpoint))
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
        request_counter = metrics.get_meter("ai-governance-control-api").create_counter(
            "control_api_requests",
            unit="1",
            description="Authenticated control-plane HTTP requests by tenant",
        )
    return TelemetryProviders(tracer_provider, meter_provider, request_counter)
