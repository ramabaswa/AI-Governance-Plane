"""Tests for evidence-backed Tempo and Prometheus reads."""

import pytest

from features.observability import service
from shared.errors.exceptions import ObservabilityUnavailableError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def get(self, url, params):
        self.calls.append((url, params))
        return FakeResponse(self.responses[url])


def test_tempo_trace_results_do_not_invent_usage_fields(monkeypatch):
    response = {
        "traces": [{
            "traceID": "trace-123",
            "rootServiceName": "agentgateway",
            "rootTraceName": "POST /v1/chat/completions",
            "startTimeUnixNano": "123456789",
            "durationMs": "14.5",
        }],
    }
    fake = FakeHttpClient({"http://tempo:3200/api/search": response})
    monkeypatch.setattr(service.httpx, "Client", lambda **_: fake)
    monkeypatch.setenv("TEMPO_QUERY_URL", "http://tempo:3200")

    traces = service.list_traces("tenant-acme")
    assert traces[0].trace_id == "trace-123"
    assert traces[0].tenant_id == "tenant-acme"
    assert traces[0].duration_ms == 14.5
    assert not hasattr(traces[0], "prompt_tokens")


def test_prometheus_returns_observed_values_and_explicit_unconfigured_metrics(monkeypatch):
    response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{"metric": {"tenant_id": "tenant-acme"}, "value": [1234, "7"]}],
        },
    }
    fake = FakeHttpClient({"http://prometheus:9090/api/v1/query": response})
    monkeypatch.setattr(service.httpx, "Client", lambda **_: fake)
    monkeypatch.setenv("PROMETHEUS_QUERY_URL", "http://prometheus:9090")
    monkeypatch.delenv("PROMETHEUS_GATEWAY_REQUESTS_QUERY", raising=False)
    monkeypatch.delenv("PROMETHEUS_INPUT_TOKENS_QUERY", raising=False)
    monkeypatch.delenv("PROMETHEUS_OUTPUT_TOKENS_QUERY", raising=False)
    monkeypatch.delenv("PROMETHEUS_ERRORS_QUERY", raising=False)

    metrics = service.query_metrics("tenant-acme")
    assert metrics["control_api_requests"]["values"] == [{"timestamp": 1234.0, "value": 7.0}]
    assert metrics["control_api_requests"]["series_found"] is True
    assert metrics["input_tokens"]["available"] is False


def test_observability_source_absence_is_an_explicit_error(monkeypatch):
    monkeypatch.delenv("TEMPO_QUERY_URL", raising=False)
    with pytest.raises(ObservabilityUnavailableError):
        service.list_traces("tenant-acme")
