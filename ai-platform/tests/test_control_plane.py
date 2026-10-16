"""API tests for the implemented tenant-scoped A-F governance slice."""

import json

from sqlalchemy import select

from shared.authorization.jwt_handler import DEVELOPMENT_ISSUER, create_access_token
from shared.authorization.roles import Role
from shared.contracts.audit import AuditAction
from features.audit_evidence.service import list_events, verify_chain
from features.gateway_traffic import service as route_service
from features.persistence import AuditEventRecord, GatewayRouteRecord
from features.persistence import TenantMembershipRecord
from shared.errors.exceptions import GatewayReconciliationError


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
        json={
            "issuer": DEVELOPMENT_ISSUER,
            "subject": "newdev@acme.internal",
            "roles": ["developer"],
        },
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
        json={
            "issuer": DEVELOPMENT_ISSUER,
            "subject": "newdev@acme.internal",
            "roles": ["developer"],
        },
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


def test_key_revocation_can_retry_failed_catalog_update(api_client):
    client, _ = api_client
    headers = auth_headers(subject="dev@acme.internal")
    created = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"name": "retry-revocation-app", "environment": "development"},
    )
    app_id = created.json()["data"]["application"]["id"]
    kubernetes_client = client.app.state.test_kubernetes_client
    apply_resources = kubernetes_client.apply
    attempts = 0

    def fail_once(resources):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise GatewayReconciliationError("temporary ConfigMap update failure")
        apply_resources(resources)

    kubernetes_client.apply = fail_once
    first_attempt = client.post(
        f"/api/v1/applications/{app_id}/keys/revoke",
        headers=headers,
    )
    assert first_attempt.status_code == 502
    assert client.get(
        f"/api/v1/applications/{app_id}/keys",
        headers=headers,
    ).json()[0]["provisioning_state"] == "revocation_pending"

    retry = client.post(
        f"/api/v1/applications/{app_id}/keys/revoke",
        headers=headers,
    )
    assert retry.status_code == 200
    assert client.get(
        f"/api/v1/applications/{app_id}/keys",
        headers=headers,
    ).json()[0]["provisioning_state"] == "revocation_submitted"

    duplicate = client.post(
        f"/api/v1/applications/{app_id}/keys/revoke",
        headers=headers,
    )
    assert duplicate.status_code == 404
    assert attempts == 2


def test_failed_key_provisioning_reports_cleanup_failure_and_can_be_retried(api_client):
    client, _ = api_client
    headers = auth_headers(subject="dev@acme.internal")
    kubernetes_client = client.app.state.test_kubernetes_client
    apply_resources = kubernetes_client.apply
    attempts = 0

    def fail_provisioning_and_cleanup(resources):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise GatewayReconciliationError("temporary ConfigMap update failure")
        apply_resources(resources)

    kubernetes_client.apply = fail_provisioning_and_cleanup
    created = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"name": "failed-provisioning-app", "environment": "development"},
    )
    assert created.status_code == 502
    assert created.json()["error"]["details"][0]["credential_cleanup_failed"] is True
    app_id = client.get("/api/v1/applications", headers=headers).json()[0]["id"]
    key_status = client.get(
        f"/api/v1/applications/{app_id}/keys",
        headers=headers,
    ).json()[0]
    assert key_status["is_revoked"] is True
    assert key_status["provisioning_state"] == "failed"

    retry = client.post(
        f"/api/v1/applications/{app_id}/keys/revoke",
        headers=headers,
    )
    assert retry.status_code == 200
    assert client.get(
        f"/api/v1/applications/{app_id}/keys",
        headers=headers,
    ).json()[0]["provisioning_state"] == "revocation_submitted"
    assert attempts == 3


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


def test_production_activation_requires_approved_separate_requester(api_client):
    client, _ = api_client
    created = client.post(
        "/api/v1/applications",
        headers=auth_headers(subject="dev@acme.internal"),
        json={"name": "approved-prod-agent", "environment": "production"},
    )
    app_id = created.json()["data"]["application"]["id"]
    approval = client.post(
        "/api/v1/approvals",
        headers=auth_headers(subject="dev@acme.internal"),
        json={
            "policy_type": "application_activation",
            "target_resource_id": app_id,
            "target_environment": "production",
            "change_summary": "Approve production activation",
            "proposed_diff": "{\"lifecycle_state\":\"active\"}",
        },
    )
    assert approval.status_code == 201
    approval_id = approval.json()["id"]

    self_decision = client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        headers=auth_headers(subject="dev@acme.internal"),
        json={"decision": "approved"},
    )
    assert self_decision.status_code == 403

    approved = client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        headers=auth_headers(subject="admin@acme.internal"),
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    activated = client.post(
        f"/api/v1/applications/{app_id}/lifecycle",
        headers=auth_headers(subject="admin@acme.internal"),
        json={"target_state": "active", "approval_request_id": approval_id},
    )
    assert activated.status_code == 200
    data = activated.json()["data"]
    assert data["application"]["lifecycle_state"] == "active"
    assert data["virtual_key"].startswith("agw_live_")

    used_again = client.post(
        f"/api/v1/applications/{app_id}/lifecycle",
        headers=auth_headers(subject="admin@acme.internal"),
        json={"target_state": "active", "approval_request_id": approval_id},
    )
    assert used_again.status_code == 409


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


def test_route_status_transitions_replace_stale_observed_state(api_client):
    client, sessions = api_client
    headers = auth_headers()
    created = client.post(
        "/api/v1/routes",
        headers=headers,
        json={
            "name": "status-route",
            "path_prefix": "/v1/status-route",
            "backend_model_id": "model-claude-35",
        },
    )
    route_id = created.json()["id"]

    class StatusReconciler:
        state = "observed_active"

        def read_status(self, _route, _models):
            return {
                "state": self.state,
                "observed_active": self.state == "observed_active",
                "resources": [],
            }

    reconciler = StatusReconciler()
    with sessions.begin() as session:
        active = route_service.get_route_status(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
            reconciler=reconciler,
        )
        assert active["state"] == "observed_active"

    reconciler.state = "pending"
    with sessions.begin() as session:
        pending = route_service.get_route_status(
            session,
            tenant_id="tenant-acme",
            route_id=route_id,
            reconciler=reconciler,
        )
        assert pending["state"] == "pending"

    with sessions() as session:
        route = session.get(GatewayRouteRecord, route_id)
        assert route.lifecycle_state == "pending"
        actions = set(session.scalars(
            select(AuditEventRecord.action).where(
                AuditEventRecord.resource_id == route_id,
            )
        ).all())
        assert AuditAction.ROUTE_OBSERVED_ACTIVE.value in actions
        assert AuditAction.ROUTE_STATUS_CHANGED.value in actions


def test_membership_resolution_is_scoped_by_oidc_issuer(api_client):
    client, sessions = api_client
    other_issuer = "https://other.identity.example.test/"
    with sessions.begin() as session:
        session.add(TenantMembershipRecord(
            issuer=other_issuer,
            subject="dev@acme.internal",
            tenant_id="tenant-globex",
            roles=[Role.TENANT_ADMIN.value],
            created_at=0,
        ))
    token = create_access_token(
        subject="dev@acme.internal",
        tenant_id="tenant-acme",
        roles=[Role.PLATFORM_ADMIN],
        extra_claims={"iss": other_issuer},
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["issuer"] == other_issuer
    assert response.json()["data"]["tenant_id"] == "tenant-globex"
    assert response.json()["data"]["roles"] == [Role.TENANT_ADMIN.value]


def test_platform_admin_cross_tenant_context_is_audited(api_client):
    client, sessions = api_client
    response = client.get(
        "/api/v1/applications",
        headers=auth_headers(tenant_id="tenant-globex", subject="root@platform.internal"),
    )
    assert response.status_code == 200

    with sessions() as session:
        events = session.scalars(
            select(AuditEventRecord).where(
                AuditEventRecord.tenant_id == "platform",
                AuditEventRecord.action == AuditAction.PLATFORM_TENANT_CONTEXT_SELECTED.value,
            )
        ).all()
        assert len(events) == 1
        assert events[0].actor == f"{DEVELOPMENT_ISSUER}#root@platform.internal"
        assert events[0].resource_id == "tenant-globex"


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


def test_openapi_exposes_governance_routes_without_inference_proxy(api_client):
    client, _ = api_client
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/chat/completions" not in paths
    assert "/api/v1/approvals" in paths
    assert "/api/v1/finops/budgets" in paths
    assert "/api/v1/mcp/servers" in paths
    assert "/api/v1/onboarding/requests" in paths
    assert "/api/v1/operations/drift" in paths
    assert "/api/v1/policies/routes/{route_id}/revisions" in paths
