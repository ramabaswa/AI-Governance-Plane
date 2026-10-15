"""Application registry backed by PostgreSQL."""

import hashlib
import json
import secrets
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.application_agent_registry.naming import tenant_api_key_configmap_name, tenant_fingerprint
from features.persistence import ApplicationRecord, ModelBackendRecord, VirtualKeyRecord
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from shared.contracts.application import (
    Application,
    ApplicationCreate,
    ApplicationLifecycle,
    VirtualKey,
    VirtualKeyStatus,
)
from shared.contracts.audit import AuditAction
from shared.errors.exceptions import GatewayReconciliationError, ResourceNotFoundError, ValidationError
from shared.errors.exceptions import PolicyApprovalRequiredError


def list_applications(session: Session, tenant_id: str) -> list[Application]:
    rows = session.scalars(
        select(ApplicationRecord)
        .where(ApplicationRecord.tenant_id == tenant_id)
        .order_by(ApplicationRecord.created_at.desc())
    ).all()
    return [Application.model_validate(row, from_attributes=True) for row in rows]


def get_application(session: Session, tenant_id: str, app_id: str) -> Application:
    row = session.scalar(
        select(ApplicationRecord).where(
            ApplicationRecord.id == app_id,
            ApplicationRecord.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ResourceNotFoundError("Application", app_id)
    return Application.model_validate(row, from_attributes=True)


def create_application(
    session: Session,
    *,
    tenant_id: str,
    created_by: str,
    request: ApplicationCreate,
    kubernetes_client: AgentgatewayKubernetesClient,
) -> tuple[Application, str | None]:
    if request.allowed_models:
        allowed = set(
            session.scalars(
                select(ModelBackendRecord.name).where(
                    ModelBackendRecord.tenant_id == tenant_id,
                    ModelBackendRecord.is_active.is_(True),
                )
            ).all()
        )
        unknown_models = sorted(set(request.allowed_models) - allowed)
        if unknown_models:
            raise ValidationError(
                "Application references models that are not approved for this tenant",
                details=[{"field": "allowed_models", "unknown": unknown_models}],
            )

    app_id = f"app-{uuid.uuid4().hex[:12]}"
    raw_key = (
        f"agw_live_{secrets.token_urlsafe(32)}"
        if request.environment != "production"
        else None
    )
    key_prefix = raw_key[:16] if raw_key else None
    now = int(time.time())
    lifecycle = (
        ApplicationLifecycle.ACTIVE
        if request.environment == "development"
        else ApplicationLifecycle.DRAFT
    )
    app_row = ApplicationRecord(
        id=app_id,
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        environment=request.environment,
        allowed_models=request.allowed_models,
        monthly_token_quota=request.monthly_token_quota,
        lifecycle_state=lifecycle.value,
        created_by=created_by,
        created_at=now,
        updated_at=now,
        virtual_key_prefix=key_prefix,
    )
    session.add(app_row)
    key_row: VirtualKeyRecord | None = None
    if raw_key is not None:
        key_row = VirtualKeyRecord(
            id=f"vk-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            application_id=app_id,
            key_prefix=key_prefix,
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            created_at=now,
            is_revoked=False,
            provisioning_state="pending",
        )
        session.add(key_row)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=created_by,
        action=AuditAction.APPLICATION_CREATED,
        resource_type="application",
        resource_id=app_id,
        details={"name": request.name, "environment": request.environment},
    )
    if raw_key is not None:
        append_event(
            session,
            tenant_id=tenant_id,
            actor=created_by,
            action=AuditAction.VIRTUAL_KEY_MINTED,
            resource_type="application",
            resource_id=app_id,
            details={"key_prefix": key_prefix},
        )
    session.flush()
    session.commit()
    if raw_key is None:
        return Application.model_validate(app_row, from_attributes=True), None
    if key_row is None:
        raise RuntimeError("Application credential record was not created")

    try:
        kubernetes_client.apply([
            tenant_api_key_configmap(
                session,
                tenant_id=tenant_id,
                include_pending_key_ids={key_row.id},
            )
        ])
    except GatewayReconciliationError as error:
        key_row.is_revoked = True
        key_row.provisioning_state = "failed"
        append_event(
            session,
            tenant_id=tenant_id,
            actor=created_by,
            action=AuditAction.VIRTUAL_KEY_PROVISION_FAILED,
            resource_type="application",
            resource_id=app_id,
            details={"key_prefix": key_prefix},
        )
        session.commit()
        try:
            kubernetes_client.apply([tenant_api_key_configmap(session, tenant_id=tenant_id)])
        except GatewayReconciliationError as cleanup_error:
            error.details.append({"credential_cleanup_failed": True, "reason": cleanup_error.message})
        raise error
    key_row.provisioning_state = "catalog_configured"
    append_event(
        session,
        tenant_id=tenant_id,
        actor=created_by,
        action=AuditAction.VIRTUAL_KEY_PROVISIONED,
        resource_type="application",
        resource_id=app_id,
        details={"key_prefix": key_prefix},
    )
    session.commit()
    return Application.model_validate(app_row, from_attributes=True), raw_key


def revoke_application_keys(
    session: Session,
    *,
    tenant_id: str,
    app_id: str,
    actor: str,
    kubernetes_client: AgentgatewayKubernetesClient,
) -> None:
    get_application(session, tenant_id, app_id)
    keys = session.scalars(
        select(VirtualKeyRecord).where(
            VirtualKeyRecord.tenant_id == tenant_id,
            VirtualKeyRecord.application_id == app_id,
            (VirtualKeyRecord.is_revoked.is_(False))
            | (VirtualKeyRecord.provisioning_state.in_(["revocation_pending", "revocation_submitted"])),
        )
    ).all()
    if not keys:
        raise ResourceNotFoundError("Active application credential", app_id)
    for key in keys:
        key.is_revoked = True
        key.provisioning_state = "revocation_pending"
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.VIRTUAL_KEY_REVOCATION_REQUESTED,
        resource_type="application",
        resource_id=app_id,
        details={"revoked_credentials": len(keys)},
    )
    session.commit()
    kubernetes_client.apply([tenant_api_key_configmap(session, tenant_id=tenant_id)])
    for key in keys:
        key.provisioning_state = "revocation_submitted"
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.VIRTUAL_KEY_REVOCATION_SUBMITTED,
        resource_type="application",
        resource_id=app_id,
        details={"revoked_credentials": len(keys), "runtime_observation": "unverified"},
    )
    session.commit()


def update_application_lifecycle(
    session: Session,
    *,
    tenant_id: str,
    app_id: str,
    target_state: ApplicationLifecycle,
    actor: str,
    kubernetes_client: AgentgatewayKubernetesClient,
) -> Application:
    row = session.scalar(
        select(ApplicationRecord).where(
            ApplicationRecord.id == app_id,
            ApplicationRecord.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ResourceNotFoundError("Application", app_id)
    if row.environment == "production" and target_state == ApplicationLifecycle.ACTIVE:
        raise PolicyApprovalRequiredError(
            "Production applications cannot be activated while the approval workflow is unavailable"
        )
    previous_state = row.lifecycle_state
    row.lifecycle_state = target_state.value
    row.updated_at = int(time.time())
    keys = []
    if target_state in {ApplicationLifecycle.SUSPENDED, ApplicationLifecycle.REJECTED}:
        keys = session.scalars(
            select(VirtualKeyRecord).where(
                VirtualKeyRecord.tenant_id == tenant_id,
                VirtualKeyRecord.application_id == app_id,
                VirtualKeyRecord.is_revoked.is_(False),
            )
        ).all()
        for key in keys:
            key.is_revoked = True
            key.provisioning_state = "revocation_pending"
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.APPLICATION_LIFECYCLE_CHANGED,
        resource_type="application",
        resource_id=app_id,
        details={"from": previous_state, "to": target_state.value},
    )
    session.flush()
    if keys:
        append_event(
            session,
            tenant_id=tenant_id,
            actor=actor,
            action=AuditAction.VIRTUAL_KEY_REVOCATION_REQUESTED,
            resource_type="application",
            resource_id=app_id,
            details={"reason": f"application_{target_state.value}", "key_count": len(keys)},
        )
    session.commit()
    if keys:
        kubernetes_client.apply([tenant_api_key_configmap(session, tenant_id=tenant_id)])
        for key in keys:
            key.provisioning_state = "revocation_submitted"
        append_event(
            session,
            tenant_id=tenant_id,
            actor=actor,
            action=AuditAction.VIRTUAL_KEY_REVOCATION_SUBMITTED,
            resource_type="application",
            resource_id=app_id,
            details={"key_count": len(keys), "runtime_observation": "unverified"},
        )
        session.commit()
    return Application.model_validate(row, from_attributes=True)


def active_virtual_keys(session: Session, tenant_id: str) -> list[VirtualKey]:
    rows = session.scalars(
        select(VirtualKeyRecord).where(
            VirtualKeyRecord.tenant_id == tenant_id,
            VirtualKeyRecord.is_revoked.is_(False),
            VirtualKeyRecord.provisioning_state == "catalog_configured",
        )
    ).all()
    return [VirtualKey.model_validate(row, from_attributes=True) for row in rows]


def application_key_status(
    session: Session,
    *,
    tenant_id: str,
    app_id: str,
) -> list[VirtualKeyStatus]:
    get_application(session, tenant_id, app_id)
    rows = session.scalars(
        select(VirtualKeyRecord)
        .where(
            VirtualKeyRecord.tenant_id == tenant_id,
            VirtualKeyRecord.application_id == app_id,
        )
        .order_by(VirtualKeyRecord.created_at.desc())
    ).all()
    return [VirtualKeyStatus.model_validate(row, from_attributes=True) for row in rows]


def tenant_api_key_configmap(
    session: Session,
    *,
    tenant_id: str,
    include_pending_key_ids: set[str] | None = None,
    namespace: str = "agentgateway-system",
) -> dict:
    include_pending = include_pending_key_ids or set()
    key_rows = session.execute(
        select(VirtualKeyRecord, ApplicationRecord)
        .join(ApplicationRecord, ApplicationRecord.id == VirtualKeyRecord.application_id)
        .where(
            VirtualKeyRecord.tenant_id == tenant_id,
            ApplicationRecord.tenant_id == tenant_id,
        )
    ).all()
    data = {}
    for key, application in key_rows:
        if key.is_revoked:
            continue
        if key.provisioning_state != "catalog_configured" and key.id not in include_pending:
            continue
        data[key.id] = json.dumps({
            "keyHash": f"sha256:{key.key_hash}",
            "metadata": {
                "tenant_id": tenant_id,
                "application_id": application.id,
                "allowed_models": application.allowed_models,
            },
        }, sort_keys=True, separators=(",", ":"))

    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": tenant_api_key_configmap_name(tenant_id),
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": "ai-governance-api-keys",
                "governance-plane.io/tenant": tenant_fingerprint(tenant_id),
            },
        },
        "data": data,
    }


def finalize_pending_revocations(session: Session, tenant_id: str) -> None:
    pending = session.scalars(
        select(VirtualKeyRecord).where(
            VirtualKeyRecord.tenant_id == tenant_id,
            VirtualKeyRecord.provisioning_state == "revocation_pending",
        )
    ).all()
    for key in pending:
        key.provisioning_state = "revocation_submitted"
