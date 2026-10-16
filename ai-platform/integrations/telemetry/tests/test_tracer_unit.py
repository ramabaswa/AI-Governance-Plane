import uuid

from integrations.telemetry import tracer


def test_trace_context_has_correlation_tenant_actor_and_timestamp():
    context = tracer.create_trace_context("tenant-acme", "admin")

    assert uuid.UUID(context["correlation_id"])
    assert context["tenant_id"] == "tenant-acme"
    assert context["actor"] == "admin"
    assert isinstance(context["timestamp_ms"], int)
    assert context["timestamp_ms"] > 0
