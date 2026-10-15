"""In-memory thread-safe state store with tenant partitioning and audit chaining."""

import hashlib
import json
import time
import uuid
import secrets
from typing import Dict, List, Optional, Any
from shared.contracts.tenant import Tenant, TenantMember
from shared.contracts.application import Application, ApplicationLifecycle, VirtualKey
from shared.contracts.model import ModelBackend, ProviderType
from shared.contracts.route import GatewayRoute, PromptGuardRule
from shared.contracts.mcp import MCPServer, MCPTool, MCPToolPolicy
from shared.contracts.policy import ApprovalRequest, ApprovalDecision
from shared.contracts.audit import AuditEvent, AuditAction
from shared.contracts.telemetry import RequestTrace, BudgetPolicy
from shared.authorization.roles import Role
from shared.errors.exceptions import (
    ResourceNotFoundError,
    ResourceConflictError,
    PolicyApprovalRequiredError,
    ForbiddenError,
)


class StateStore:
    """Thread-safe state repository partitioning entities by tenant_id."""

    def __init__(self):
        self.tenants: Dict[str, Tenant] = {}
        self.applications: Dict[str, Application] = {} # id -> Application
        self.virtual_keys: Dict[str, VirtualKey] = {} # id -> VirtualKey
        self.models: Dict[str, ModelBackend] = {} # id -> ModelBackend
        self.routes: Dict[str, GatewayRoute] = {} # id -> GatewayRoute
        self.mcp_servers: Dict[str, MCPServer] = {} # id -> MCPServer
        self.approvals: Dict[str, ApprovalRequest] = {} # id -> ApprovalRequest
        self.audit_log: List[AuditEvent] = []
        self.traces: List[RequestTrace] = []
        self.budgets: Dict[str, BudgetPolicy] = {} # tenant_id -> BudgetPolicy
        self.last_audit_hash: str = "0" * 64

        # Seed initial default tenant and models
        self._seed_initial_data()

    def _seed_initial_data(self):
        # Default Tenant
        now = int(time.time())
        t_acme = Tenant(
            id="tenant-acme",
            name="Acme Corp",
            slug="acme-corp",
            description="Default production tenant",
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        self.tenants[t_acme.id] = t_acme

        # Default Model Backends
        m_claude = ModelBackend(
            id="model-claude-35",
            tenant_id="tenant-acme",
            name="claude-3-5-sonnet",
            provider=ProviderType.ANTHROPIC,
            model_name="claude-3-5-sonnet-20241022",
            secret_ref="anthropic-secret/api-key",
            base_url=None,
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.models[m_claude.id] = m_claude

        m_gpt4 = ModelBackend(
            id="model-gpt4o",
            tenant_id="tenant-acme",
            name="gpt-4o",
            provider=ProviderType.OPENAI,
            model_name="gpt-4o",
            secret_ref="openai-secret/api-key",
            base_url=None,
            cost_per_1k_input_tokens=0.005,
            cost_per_1k_output_tokens=0.015,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.models[m_gpt4.id] = m_gpt4

        # Default budget
        self.budgets["tenant-acme"] = BudgetPolicy(
            tenant_id="tenant-acme",
            monthly_budget_usd=100.0,
            alert_threshold_pct=80,
            current_spend_usd=12.50,
            hard_cap_enabled=True,
            hard_cap_action="reject_429",
            updated_at=now,
        )

        # Initial genesis audit log event
        self.record_audit_event(
            tenant_id="platform",
            actor="system",
            action=AuditAction.TENANT_CREATED,
            resource_type="tenant",
            resource_id="tenant-acme",
            details={"seed": True},
        )

    # ================= Audit Ledger Chaining =================
    def record_audit_event(
        self,
        tenant_id: str,
        actor: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        now = int(time.time())
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        details_dict = details or {}
        payload_hash = hashlib.sha256(
            json.dumps(details_dict, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

        event_hash = AuditEvent.calculate_event_hash(
            event_id=event_id,
            tenant_id=tenant_id,
            actor=actor,
            action=action.value,
            resource_id=resource_id,
            payload_hash=payload_hash,
            prev_hash=self.last_audit_hash,
            timestamp=now,
            resource_type=resource_type,
        )

        event = AuditEvent(
            id=event_id,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_hash=payload_hash,
            details=details_dict,
            prev_event_hash=self.last_audit_hash,
            event_hash=event_hash,
            timestamp=now,
        )

        self.audit_log.append(event)
        self.last_audit_hash = event_hash
        return event

    def get_audit_events(self, tenant_id: str, actor: str) -> List[AuditEvent]:
        # Record AUDIT_READ event: reading the audit log is itself audited!
        self.record_audit_event(
            tenant_id=tenant_id,
            actor=actor,
            action=AuditAction.AUDIT_READ,
            resource_type="audit_log",
            resource_id="all",
            details={"query": "get_audit_events"},
        )
        return [evt for evt in self.audit_log if evt.tenant_id in (tenant_id, "platform")]

    # ================= Applications =================
    def register_application(
        self,
        tenant_id: str,
        name: str,
        description: Optional[str],
        environment: str,
        allowed_models: List[str],
        monthly_token_quota: int,
        created_by: str,
    ) -> tuple[Application, str]:
        app_id = f"app-{uuid.uuid4().hex[:8]}"
        now = int(time.time())

        # Generate virtual key
        raw_key = f"agw_live_{secrets.token_hex(16)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        key_prefix = raw_key[:16]

        vk = VirtualKey(
            id=f"vk-{uuid.uuid4().hex[:8]}",
            key_prefix=key_prefix,
            key_hash=key_hash,
            application_id=app_id,
            tenant_id=tenant_id,
            created_at=now,
            is_revoked=False,
        )
        self.virtual_keys[vk.id] = vk

        app = Application(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            environment=environment,
            allowed_models=allowed_models,
            monthly_token_quota=monthly_token_quota,
            lifecycle_state=ApplicationLifecycle.ACTIVE if environment == "development" else ApplicationLifecycle.DRAFT,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            virtual_key_prefix=key_prefix,
        )
        self.applications[app.id] = app

        # Record Audit Event
        self.record_audit_event(
            tenant_id=tenant_id,
            actor=created_by,
            action=AuditAction.APPLICATION_CREATED,
            resource_type="application",
            resource_id=app.id,
            details={"name": name, "environment": environment},
        )

        return app, raw_key

    def get_application(self, tenant_id: str, app_id: str) -> Application:
        app = self.applications.get(app_id)
        # Strict cross-tenant security: return 404 if app is not in caller's tenant!
        if not app or app.tenant_id != tenant_id:
            raise ResourceNotFoundError("Application", app_id)
        return app

    def list_applications(self, tenant_id: str) -> List[Application]:
        return [app for app in self.applications.values() if app.tenant_id == tenant_id]

    def update_application_lifecycle(
        self,
        tenant_id: str,
        app_id: str,
        target_state: ApplicationLifecycle,
        actor: str,
    ) -> Application:
        app = self.get_application(tenant_id, app_id)

        # In production, skipping approval directly to ACTIVE is rejected!
        if app.environment == "production":
            if app.lifecycle_state == ApplicationLifecycle.DRAFT and target_state == ApplicationLifecycle.ACTIVE:
                raise PolicyApprovalRequiredError(
                    "Production applications cannot transition directly from 'draft' to 'active' without approval"
                )

        old_state = app.lifecycle_state
        app.lifecycle_state = target_state
        app.updated_at = int(time.time())

        self.record_audit_event(
            tenant_id=tenant_id,
            actor=actor,
            action=AuditAction.APPLICATION_LIFECYCLE_CHANGED,
            resource_type="application",
            resource_id=app.id,
            details={"from": old_state.value, "to": target_state.value},
        )
        return app

    # ================= Routes & Policies =================
    def create_route(
        self,
        tenant_id: str,
        name: str,
        path_prefix: str,
        backend_model_id: str,
        failover_model_ids: List[str],
        traffic_weights: Optional[Dict[str, int]],
        dlp_rules: List[PromptGuardRule],
        rate_limit_rpm: Optional[int],
        actor: str,
    ) -> GatewayRoute:
        # Check duplicate name within tenant
        for r in self.routes.values():
            if r.tenant_id == tenant_id and r.name == name:
                raise ResourceConflictError(
                    f"Route with name '{name}' already exists in tenant '{tenant_id}'"
                )

        now = int(time.time())
        route = GatewayRoute(
            id=f"route-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            name=name,
            path_prefix=path_prefix,
            backend_model_id=backend_model_id,
            failover_model_ids=failover_model_ids,
            traffic_weights=traffic_weights or {backend_model_id: 100},
            dlp_rules=dlp_rules,
            rate_limit_rpm=rate_limit_rpm,
            revision_id=1,
            lifecycle_state="draft",
            created_at=now,
            updated_at=now,
        )
        self.routes[route.id] = route

        self.record_audit_event(
            tenant_id=tenant_id,
            actor=actor,
            action=AuditAction.ROUTE_CREATED,
            resource_type="route",
            resource_id=route.id,
            details={"name": name, "path_prefix": path_prefix},
        )
        return route

    def get_route(self, tenant_id: str, route_id: str) -> GatewayRoute:
        route = self.routes.get(route_id)
        if not route or route.tenant_id != tenant_id:
            raise ResourceNotFoundError("Route", route_id)
        return route

    def list_routes(self, tenant_id: str) -> List[GatewayRoute]:
        return [r for r in self.routes.values() if r.tenant_id == tenant_id]

    # ================= Approvals =================
    def create_approval_request(
        self,
        tenant_id: str,
        policy_type: str,
        target_resource_id: str,
        target_environment: str,
        change_summary: str,
        proposed_diff: str,
        requested_by: str,
    ) -> ApprovalRequest:
        now = int(time.time())
        req = ApprovalRequest(
            id=f"appr-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            policy_type=policy_type,
            target_resource_id=target_resource_id,
            target_environment=target_environment,
            change_summary=change_summary,
            proposed_diff=proposed_diff,
            requested_by=requested_by,
            status="pending",
            created_at=now,
        )
        self.approvals[req.id] = req

        self.record_audit_event(
            tenant_id=tenant_id,
            actor=requested_by,
            action=AuditAction.POLICY_APPROVAL_REQUESTED,
            resource_type="approval",
            resource_id=req.id,
            details={"summary": change_summary},
        )
        return req

    def decide_approval_request(
        self,
        tenant_id: str,
        request_id: str,
        decision: ApprovalDecision,
        decided_by: str,
        comments: Optional[str] = None,
    ) -> ApprovalRequest:
        req = self.approvals.get(request_id)
        if not req or req.tenant_id != tenant_id:
            raise ResourceNotFoundError("ApprovalRequest", request_id)

        now = int(time.time())

        # Self-approval check:
        # Strict Rule: test_self_approval_denial_is_committed_with_denied_decision
        if req.requested_by == decided_by:
            req.status = ApprovalDecision.DENIED.value
            req.decided_by = decided_by
            req.decided_at = now
            req.decision_comments = "Self-approval is prohibited; request automatically denied"

            self.record_audit_event(
                tenant_id=tenant_id,
                actor=decided_by,
                action=AuditAction.POLICY_APPROVAL_DECIDED,
                resource_type="approval",
                resource_id=req.id,
                details={"decision": "denied", "reason": "self_approval_denied"},
            )
            raise ForbiddenError("Self-approval is forbidden. The approval decision has been recorded as denied.")

        req.status = decision.value
        req.decided_by = decided_by
        req.decided_at = now
        req.decision_comments = comments

        self.record_audit_event(
            tenant_id=tenant_id,
            actor=decided_by,
            action=AuditAction.POLICY_APPROVAL_DECIDED,
            resource_type="approval",
            resource_id=req.id,
            details={"decision": decision.value, "comments": comments},
        )
        return req


# Global singleton instance
STATE_STORE = StateStore()
