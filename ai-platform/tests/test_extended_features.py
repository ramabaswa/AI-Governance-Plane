"""Tests for approvals, onboarding, FinOps, MCP, operations, and policy history."""

from features.gateway_traffic import service as route_service
from features.persistence import GatewayRouteRecord
from features.policy_lifecycle import service as policy_service
from shared.authorization.jwt_handler import create_access_token


def _headers(subject="admin@acme.internal", tenant_id="tenant-acme"):
    token = create_access_token(subject=subject, tenant_id="ignored", roles=[])
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


def test_onboarding_requires_reviewer_and_only_requester_can_complete(api_client):
    client, _ = api_client
    request = client.post(
        "/api/v1/onboarding/requests",
        headers=_headers("dev@acme.internal"),
        json={
            "application_name": "onboarded-agent",
            "environment": "development",
            "requested_models": [],
        },
    )
    assert request.status_code == 201
    request_id = request.json()["id"]

    approved = client.post(
        f"/api/v1/onboarding/requests/{request_id}/review",
        headers=_headers(),
        json={"decision": "approved"},
    )
    assert approved.status_code == 200

    wrong_user = client.post(
        f"/api/v1/onboarding/requests/{request_id}/complete",
        headers=_headers(),
    )
    assert wrong_user.status_code == 403

    completed = client.post(
        f"/api/v1/onboarding/requests/{request_id}/complete",
        headers=_headers("dev@acme.internal"),
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["virtual_key"].startswith("agw_live_")
    assert completed.json()["data"]["request"]["status"] == "completed"


def test_finops_reports_unknown_spend_and_rejects_unavailable_hard_cap(api_client):
    client, _ = api_client
    headers = _headers()
    updated = client.put(
        "/api/v1/finops/budgets",
        headers=headers,
        json={
            "monthly_budget_usd": 250,
            "alert_threshold_pct": 75,
            "hard_cap_enabled": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["configured"] is True
    assert updated.json()["current_spend_usd"] is None
    assert updated.json()["hard_cap_enforcement"] == "unavailable"

    unsupported = client.put(
        "/api/v1/finops/budgets",
        headers=headers,
        json={
            "monthly_budget_usd": 250,
            "alert_threshold_pct": 75,
            "hard_cap_enabled": True,
        },
    )
    assert unsupported.status_code == 422
    assert "Hard-cap enforcement is not available" in unsupported.json()["error"]["message"]


def test_mcp_discovery_uses_real_protocol_and_enforces_host_allowlist(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.test")

    class FakeResponse:
        def __init__(self, *, status_code=200, body=None, headers=None):
            self.status_code = status_code
            self._body = body or {}
            self.headers = headers or {}
            self.text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class FakeHttpClient:
        calls = []

        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, _url, *, json, headers):
            self.calls.append((json.get("method"), headers))
            if json.get("method") == "initialize":
                return FakeResponse(
                    body={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26"}},
                    headers={"MCP-Session-Id": "session-test"},
                )
            if json.get("method") == "notifications/initialized":
                return FakeResponse(status_code=202)
            return FakeResponse(body={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"tools": [{"name": "lookup", "inputSchema": {"type": "object"}}]},
            })

    monkeypatch.setattr("features.mcp_governance.service.httpx.Client", FakeHttpClient)
    registered = client.post(
        "/api/v1/mcp/servers",
        headers=_headers(),
        json={"name": "catalog-server", "transport_url": "https://mcp.example.test/rpc"},
    )
    assert registered.status_code == 201
    assert registered.json()["discovery_state"] == "unverified"
    assert registered.json()["policy_enforcement_state"] == "not_published_to_gateway"

    server_id = registered.json()["id"]
    discovered = client.post(
        f"/api/v1/mcp/servers/{server_id}/discover",
        headers=_headers(),
    )
    assert discovered.status_code == 200
    assert discovered.json()["discovery_state"] == "discovered"
    assert discovered.json()["discovered_tools"][0]["name"] == "lookup"
    assert discovered.json()["discovered_tools"][0]["is_sensitive"] is True
    assert discovered.json()["discovered_tools"][0]["requires_hitl_approval"] is True
    assert FakeHttpClient.calls[1][0] == "notifications/initialized"


def test_mcp_discovery_refuses_unallowlisted_hosts_without_network_access(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    registered = client.post(
        "/api/v1/mcp/servers",
        headers=_headers(),
        json={"name": "untrusted-server", "transport_url": "https://mcp.example.test/rpc"},
    )
    response = client.post(
        f"/api/v1/mcp/servers/{registered.json()['id']}/discover",
        headers=_headers(),
    )
    assert response.status_code == 422
    assert "allowlist" in response.json()["error"]["message"]


def test_policy_revisions_are_persisted_and_rollback_creates_a_new_revision(api_client):
    client, sessions = api_client
    created = client.post(
        "/api/v1/routes",
        headers=_headers(),
        json={
            "name": "versioned-route",
            "path_prefix": "/v1/original",
            "backend_model_id": "model-claude-35",
        },
    )
    assert created.status_code == 201
    route_id = created.json()["id"]

    class PendingReconciler:
        def apply(self, *_args, **_kwargs):
            return None

        def read_status(self, *_args, **_kwargs):
            return {"state": "pending", "observed_active": False, "resources": []}

    reconciler = PendingReconciler()
    with sessions() as session:
        route_service.apply_route(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
            actor="admin@acme.internal",
            reconciler=reconciler,
        )
    with sessions() as session:
        row = session.get(GatewayRouteRecord, route_id)
        row.path_prefix = "/v1/changed"
        session.commit()
    with sessions() as session:
        route_service.apply_route(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
            actor="admin@acme.internal",
            reconciler=reconciler,
        )
    with sessions() as session:
        policy_service.prepare_route_rollback(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
            revision_number=2,
            actor="admin@acme.internal",
        )
        route_service.apply_route(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
            actor="admin@acme.internal",
            reconciler=reconciler,
        )
    with sessions() as session:
        row = session.get(GatewayRouteRecord, route_id)
        revisions = policy_service.list_route_revisions(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
        )
        assert row.path_prefix == "/v1/original"
        assert [revision.revision for revision in revisions] == [4, 3, 2]
        assert revisions[0].snapshot["path_prefix"] == "/v1/original"


def test_operations_drift_endpoint_is_read_only_and_tenant_scoped(api_client):
    client, _ = api_client
    response = client.get("/api/v1/operations/drift", headers=_headers())
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-acme"
    assert response.json()["write_performed"] is False
    assert response.json()["routes"] == []
