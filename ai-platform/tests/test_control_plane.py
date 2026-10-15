"""API tests for the implemented tenant-scoped A-F governance slice."""

import json

from shared.authorization.jwt_handler import create_access_token
from shared.authorization.roles import Role
from shared.contracts.audit import AuditAction
from features.audit_evidence.service import list_events, verify_chain
from features.persistence import AuditEventRecord


def auth_headers(tenant_id="tenant-acme", subject="admin@acme.internal", claimed_role=Role.VIEWER):
    token = create_access_token(subject=subject, tenant_id="untrusted-claim", roles=[claimed_role])
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


def test_local_login_is_disabled_outside_development(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setenv("ENVIRONMENT", "production")
    response = client.post("/api/v1/auth/token", json={
        "username": "admin@acme.internal",
        "password": "devpassword123!",
    })
    assert response.status_code == 401


def test_client_cannot_choose_unassigned_tenant(api_client):
    client, _ = api_client
    headers = auth_headers(subject="dev@acme.internal")
    headers["X-Tenant-ID"] = "tenant-globex"
    response = client.get("/api/v1/applications", headers=headers)
    assert response.status_code == 403


def test_platform_admin_can_manage_tenant_memberships(api_client):
    client, _ = api_client
    platform_headers = auth_headers(
        tenant_id="platform",
        subject="root@platform.internal",
    )
    created = client.post(
        "/api/v1/tenants/tenant-acme/memberships",
        headers=platform_headers,
        json={"subject": "newdev@acme.internal", "roles": ["developer"]},
    )
    assert created.status_code == 201

    tenant_headers = auth_headers(
        tenant_id="tenant-acme",
        subject="newdev@acme.internal",
    )
    assert client.get("/api/v1/applications", headers=tenant_headers).status_code == 200


def test_tenant_admin_cannot_manage_memberships(api_client):
    client, _ = api_client
    response = client.post(
        "/api/v1/tenants/tenant-acme/memberships",
        headers=auth_headers(subject="admin@acme.internal"),
        json={"subject": "newdev@acme.internal", "roles": ["developer"]},
    )
    assert response.status_code == 403


def test_role_claims_do_not_grant_tenant_authority(api_client):
    client, _ = api_client
    response = client.post(
        "/api/v1/models",
        headers=auth_headers(subject="dev@acme.internal", claimed_role=Role.PLATFORM_ADMIN),
        json={
            "name": "claimed-admin-model",
            "provider": "anthropic",
            "model_name": "claude-test",
            "secret_ref": "anthropic-secret/api-key",
        },
    )
    assert response.status_code == 403


def test_application_registration_is_tenant_scoped_and_key_is_one_time(api_client):
    client, _ = api_client
    headers = auth_headers(subject="dev@acme.internal")
    response = client.post(
        "/api/v1/applications",
        headers=headers,
        json={
            "name": "dev-bot-service",
            "environment": "development",
            "allowed_models": ["claude-3-5-sonnet"],
        },
    )
    assert response.status_code == 201
    body = response.json()["data"]
    app_id = body["application"]["id"]
    assert body["virtual_key"].startswith("agw_live_")
    assert "virtual_key" not in client.get(
        f"/api/v1/applications/{app_id}", headers=headers
    ).json()
    assert client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("tenant-globex", "dev@globex.internal"),
    ).status_code == 404
    configmap = client.app.state.test_kubernetes_client.resources[0]
    assert configmap["kind"] == "ConfigMap"
    stored_key = json.loads(next(iter(configmap["data"].values())))
    assert stored_key["keyHash"].startswith("sha256:")
    assert body["virtual_key"] not in configmap["data"].values()


def test_key_revocation_updates_the_desired_key_catalog(api_client):
    client, _ = api_client
    headers = auth_headers(subject="dev@acme.internal")
    created = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"name": "revocation-app", "environment": "development"},
    )
    app_id = created.json()["data"]["application"]["id"]

    response = client.post(f"/api/v1/applications/{app_id}/keys/revoke", headers=headers)
    assert response.status_code == 200
    configmap = client.app.state.test_kubernetes_client.resources[-1]
    assert configmap["data"] == {}


def test_production_application_cannot_skip_approval(api_client):
    client, _ = api_client
    headers = auth_headers()
    created = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"name": "prod-claims-agent", "environment": "production"},
    )
    assert created.status_code == 201
    data = created.json()["data"]
    app_id = data["application"]["id"]
    assert data["virtual_key"] is None
    assert data["credential_state"] == "not_issued_approval_required"
    assert data["application"]["lifecycle_state"] == "draft"
    assert data["application"]["virtual_key_prefix"] is None
    assert client.get(
        f"/api/v1/applications/{app_id}/keys",
        headers=headers,
    ).json() == []
    assert client.app.state.test_kubernetes_client.resources == []

    suspended = client.post(
        f"/api/v1/applications/{app_id}/lifecycle",
        headers=headers,
        json={"target_state": "suspended"},
    )
    assert suspended.status_code == 200
    response = client.post(
        f"/api/v1/applications/{app_id}/lifecycle",
        headers=headers,
        json={"target_state": "active"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "APPROVAL_REQUIRED"


def test_duplicate_route_conflicts_and_validation_only_emits_candidate_resources(api_client):
    client, _ = api_client
    headers = auth_headers()
    payload = {
        "name": "unique-chat-route",
        "path_prefix": "/v1/unique-chat",
        "backend_model_id": "model-claude-35",
        "dlp_rules": [{
            "name": "mask-card",
            "regex_patterns": [r"\b4[0-9]{12}(?:[0-9]{3})?\b"],
            "action": "Mask",
        }],
    }
    first = client.post("/api/v1/routes", headers=headers, json=payload)
    assert first.status_code == 201
    assert client.post("/api/v1/routes", headers=headers, json=payload).status_code == 409

    validated = client.post("/api/v1/routes/validate", headers=headers, json=payload)
    assert validated.status_code == 200
    result = validated.json()
    assert result["status"] == "validated"
    assert "AgentgatewayBackend" in result["kubernetes_crds"]
    assert "AgentgatewayPolicy" in result["kubernetes_crds"]
    assert "observed_active" not in result["status"]


def test_audit_read_is_chained_and_itself_audited(api_client):
    client, sessions = api_client
    with sessions() as session:
        events = list_events(
            session,
            tenant_id="tenant-acme",
            actor="auditor@acme.internal",
            limit=100,
        )
        session.commit()
        assert any(event.action == AuditAction.AUDIT_READ for event in events)
        assert verify_chain(session, tenant_id="tenant-acme")


def test_audit_chain_detects_mutated_event_details(api_client):
    client, sessions = api_client
    with sessions() as session:
        list_events(session, tenant_id="tenant-acme", actor="auditor@acme.internal")
        session.commit()
        row = session.query(AuditEventRecord).filter_by(tenant_id="tenant-acme").first()
        row.details = {"tampered": True}
        session.commit()
        assert verify_chain(session, tenant_id="tenant-acme") is False


def test_openapi_excludes_deferred_features_and_inference_proxy(api_client):
    client, _ = api_client
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/chat/completions" not in paths
    assert not any(path.startswith("/api/v1/mcp") for path in paths)
    assert not any(path.startswith("/api/v1/approvals") for path in paths)
