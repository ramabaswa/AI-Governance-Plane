"""Queries Tempo and Prometheus; never synthesizes sample observability values."""

import json
import os
import time
from typing import Any

import httpx

from shared.contracts.telemetry import ObservedTrace
from shared.errors.exceptions import ObservabilityUnavailableError


def list_traces(tenant_id: str, *, limit: int = 50) -> list[ObservedTrace]:
    tempo_url = os.getenv("TEMPO_QUERY_URL")
    if not tempo_url:
        raise ObservabilityUnavailableError("Tempo", "TEMPO_QUERY_URL is not configured")
    now = int(time.time())
    traceql = f'{{ span.tenant.id = {json.dumps(tenant_id)} }}'
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{tempo_url.rstrip('/')}/api/search",
                params={"q": traceql, "start": now - 3600, "end": now, "limit": limit},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ObservabilityUnavailableError("Tempo", "trace search request failed") from error

    if not isinstance(payload, dict):
        raise ObservabilityUnavailableError("Tempo", "trace search response has an invalid shape")
    traces = payload.get("traces")
    if not isinstance(traces, list):
        raise ObservabilityUnavailableError("Tempo", "trace search response has an invalid shape")
    observed = []
    for item in traces:
        if not isinstance(item, dict) or not isinstance(item.get("traceID"), str):
            raise ObservabilityUnavailableError("Tempo", "trace search returned a malformed trace")
        observed.append(ObservedTrace(
            trace_id=item["traceID"],
            tenant_id=tenant_id,
            root_service_name=item.get("rootServiceName"),
            root_trace_name=item.get("rootTraceName"),
            start_time_unix_nano=_optional_int(item.get("startTimeUnixNano")),
            duration_ms=_optional_float(item.get("durationMs")),
        ))
    return observed


def query_metrics(tenant_id: str) -> dict[str, Any]:
    prometheus_url = os.getenv("PROMETHEUS_QUERY_URL")
    if not prometheus_url:
        raise ObservabilityUnavailableError("Prometheus", "PROMETHEUS_QUERY_URL is not configured")
    query_templates = {
        "control_api_requests": os.getenv(
            "PROMETHEUS_CONTROL_API_REQUESTS_QUERY",
            'sum(control_api_requests_total{tenant_id="{tenant_id}"})',
        ),
        "gateway_requests": os.getenv("PROMETHEUS_GATEWAY_REQUESTS_QUERY"),
        "input_tokens": os.getenv("PROMETHEUS_INPUT_TOKENS_QUERY"),
        "output_tokens": os.getenv("PROMETHEUS_OUTPUT_TOKENS_QUERY"),
        "errors": os.getenv("PROMETHEUS_ERRORS_QUERY"),
    }

    results: dict[str, Any] = {}
    try:
        with httpx.Client(timeout=5.0) as client:
            for name, template in query_templates.items():
                if not template:
                    results[name] = {
                        "available": False,
                        "reason": "tenant-scoped query template is not configured",
                        "values": None,
                    }
                    continue
                if "{tenant_id}" not in template:
                    raise ObservabilityUnavailableError(
                        "Prometheus",
                        f"{name} query template must include the tenant_id variable",
                    )
                query = template.replace("{tenant_id}", json.dumps(tenant_id))
                response = client.get(
                    f"{prometheus_url.rstrip('/')}/api/v1/query",
                    params={"query": query},
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "success" or not isinstance(payload.get("data"), dict):
                    raise ObservabilityUnavailableError(
                        "Prometheus",
                        f"{name} query returned an invalid response",
                    )
                data = payload["data"]
                series = data.get("result")
                if not isinstance(series, list) or any(not isinstance(item, dict) for item in series):
                    raise ObservabilityUnavailableError(
                        "Prometheus",
                        f"{name} query returned an invalid result",
                    )
                results[name] = {
                    "available": True,
                    "result_type": data.get("resultType"),
                    "values": [
                        _prometheus_value(item)
                        for item in series
                    ],
                    "series_found": bool(series),
                }
    except ObservabilityUnavailableError:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise ObservabilityUnavailableError("Prometheus", "metrics query request failed") from error
    return results


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ObservabilityUnavailableError("Tempo", "trace search returned an invalid timestamp") from error


def _optional_float(value: Any, source: str = "Tempo") -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ObservabilityUnavailableError(source, "telemetry query returned an invalid number") from error


def _prometheus_value(series: dict[str, Any]) -> dict[str, Any]:
    raw_value = series.get("value")
    if not isinstance(raw_value, list) or len(raw_value) != 2:
        raise ObservabilityUnavailableError("Prometheus", "metrics query returned an invalid sample")
    return {
        "timestamp": _optional_float(raw_value[0], "Prometheus"),
        "value": _optional_float(raw_value[1], "Prometheus"),
    }
