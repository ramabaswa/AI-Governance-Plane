import pytest

from features.observability import service
from shared.errors.exceptions import ObservabilityUnavailableError


def test_tempo_trace_query_scopes_tenant_and_preserves_missing_usage(monkeypatch):
    monkeypatch.setenv("TEMPO_QUERY_URL", "https://tempo.example.test")
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"traces": [{"traceID": "trace-1"}]}

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url, *, params):
            calls.append((url, params))
            return Response()

    monkeypatch.setattr(service.httpx, "Client", Client)
    traces = service.list_traces("tenant-acme")

    assert traces[0].trace_id == "trace-1"
    assert traces[0].tenant_id == "tenant-acme"
    assert traces[0].duration_ms is None
    assert "tenant-acme" in calls[0][1]["q"]


def test_prometheus_query_requires_tenant_variable(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_QUERY_URL", "https://prometheus.example.test")
    monkeypatch.setenv("PROMETHEUS_CONTROL_API_REQUESTS_QUERY", "sum(requests_total)")
    with pytest.raises(ObservabilityUnavailableError, match="tenant_id variable"):
        service.query_metrics("tenant-acme")
