"""Opt-in checks against a deployed Control API and agentgateway runtime.

Set AGP_RUN_LIVE_INTEGRATION=1 and the required AGP_LIVE_* variables to run.
These checks use an existing, explicitly selected route and never create or
delete Kubernetes resources.
"""

import os
from urllib.parse import quote

import httpx
import pytest


pytestmark = [
    pytest.mark.live_integration,
    pytest.mark.skipif(
        os.getenv("AGP_RUN_LIVE_INTEGRATION") != "1",
        reason="Set AGP_RUN_LIVE_INTEGRATION=1 to enable live service checks",
    ),
]


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.fail(f"{name} is required when AGP_RUN_LIVE_INTEGRATION=1")
    return value


def test_live_control_api_reads_controller_observation_for_configured_route():
    base_url = _required("AGP_LIVE_CONTROL_API_URL").rstrip("/")
    token = _required("AGP_LIVE_OIDC_TOKEN")
    tenant_id = _required("AGP_LIVE_TENANT_ID")
    route_id = _required("AGP_LIVE_ROUTE_ID")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }

    with httpx.Client(timeout=20.0) as client:
        health = client.get(f"{base_url}/healthz")
        readiness = client.get(f"{base_url}/readyz")
        status = client.get(
            f"{base_url}/api/v1/routes/{quote(route_id, safe='')}/status",
            headers=headers,
        )

    assert health.status_code == 200, health.text
    assert readiness.status_code == 200, readiness.text
    assert status.status_code == 200, status.text
    observation = status.json()
    assert observation["route_id"] == route_id
    assert observation["state"] in {"observed_active", "pending", "rejected"}
    assert isinstance(observation["resources"], list)
    assert observation["resources"], "The live route status returned no Kubernetes resource observations"
    if observation["state"] == "observed_active":
        assert observation["observed_active"] is True
        assert all(resource["state"] == "accepted" for resource in observation["resources"])
    else:
        assert observation["observed_active"] is False


@pytest.mark.skipif(
    os.getenv("AGP_LIVE_ALLOW_INFERENCE_REQUEST") != "1",
    reason="Set AGP_LIVE_ALLOW_INFERENCE_REQUEST=1 to permit a real inference request",
)
def test_live_agentgateway_serves_configured_smoke_request():
    url = _required("AGP_LIVE_INFERENCE_URL")
    api_key = _required("AGP_LIVE_INFERENCE_API_KEY")
    request_json = _required("AGP_LIVE_INFERENCE_REQUEST_JSON")

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            content=request_json,
        )

    assert 200 <= response.status_code < 300, (
        f"Configured gateway smoke request failed with HTTP {response.status_code}"
    )
    assert response.content, "Gateway returned an empty response to the configured smoke request"
