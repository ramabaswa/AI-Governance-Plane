"""Relational records for tenant-scoped governance state."""

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TenantRecord(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TenantMembershipRecord(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", "tenant_id", name="uq_membership_issuer_subject_tenant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ApplicationRecord(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_application_tenant_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_models: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    monthly_token_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)
    virtual_key_prefix: Mapped[str | None] = mapped_column(String(24))


class VirtualKeyRecord(Base):
    __tablename__ = "virtual_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int | None] = mapped_column(Integer)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provisioning_state: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


class ModelBackendRecord(Base):
    __tablename__ = "model_backends"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_model_tenant_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512))
    cost_per_1k_input_tokens: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    cost_per_1k_output_tokens: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class GatewayRouteRecord(Base):
    __tablename__ = "gateway_routes"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_route_tenant_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    path_prefix: Mapped[str] = mapped_column(String(256), nullable=False)
    backend_model_id: Mapped[str] = mapped_column(ForeignKey("model_backends.id"), nullable=False)
    failover_model_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    traffic_weights: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    dlp_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    rate_limit_rpm: Mapped[int | None] = mapped_column(Integer)
    revision_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    policy_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_environment: Mapped[str] = mapped_column(String(32), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_diff: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decided_at: Mapped[int | None] = mapped_column(Integer)
    decision_comments: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)


class OnboardingRequestRecord(Base):
    __tablename__ = "onboarding_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    request_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[int | None] = mapped_column(Integer)
    review_comments: Mapped[str | None] = mapped_column(Text)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"))
    completed_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)


class BudgetPolicyRecord(Base):
    __tablename__ = "budget_policies"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    monthly_budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class MCPServerRecord(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_mcp_server_tenant_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    discovered_tools: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    policies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    discovery_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class PolicyRevisionRecord(Base):
    __tablename__ = "policy_revisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resource_id", "revision", name="uq_policy_revision_resource"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    prev_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class AuditChainHeadRecord(Base):
    __tablename__ = "audit_chain_head"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
