"""Tests for truthful, tenant-authorized platform capability reporting."""

from shared.authorization.jwt_handler import create_access_token
from shared.authorization.roles import Role


def _auth_headers():
    token = create_access_token(
        subject="admin@acme.internal",
        tenant_id="tenant-acme",
        roles=[Role.VIEWER],
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-acme"}


def test_platform_capabilities_report_target_paths_and_gateway_limitations(api_client):
    client, _ = api_client

    response = client.get(
        "/api/v1/platform/capabilities",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    capabilities = response.json()
    assert capabilities["control_plane"]["inference_proxy"] is False
    assert capabilities["gateway"]["runtime_verified"] is False
    assert capabilities["gateway"]["release"] == "v1.6.0"
    assert capabilities["gateway"]["supported_providers"] == [
        "anthropic",
        "bedrock",
        "gemini",
        "openai",
    ]
    assert capabilities["ingress"]["apim"]["status"] == "target_only"
    assert capabilities["ingress"]["direct_private"]["status"] == "target_only"
    assert capabilities["integrations"]["mcp_runtime_policy_enforcement"]["status"] == (
        "not_published_to_gateway"
    )


def test_platform_capabilities_require_authenticated_tenant_context(api_client):
    client, _ = api_client

    response = client.get("/api/v1/platform/capabilities")

    assert response.status_code == 401
