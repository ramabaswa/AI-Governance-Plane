"""Tenant-scoped approved model catalog."""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.persistence import ModelBackendRecord
from shared.contracts.audit import AuditAction
from shared.contracts.model import ModelBackend, ModelBackendCreate
from shared.errors.exceptions import ResourceConflictError, ValidationError
from shared.validation.route_validator import validate_backend_url


def list_models(session: Session, tenant_id: str) -> list[ModelBackend]:
    rows = session.scalars(
        select(ModelBackendRecord)
        .where(ModelBackendRecord.tenant_id == tenant_id)
        .order_by(ModelBackendRecord.name)
    ).all()
    return [ModelBackend.model_validate(row, from_attributes=True) for row in rows]


def get_tenant_models(session: Session, tenant_id: str) -> dict[str, ModelBackend]:
    return {model.id: model for model in list_models(session, tenant_id)}


def create_model(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: ModelBackendCreate,
) -> ModelBackend:
    if request.base_url:
        validate_backend_url(request.base_url)
        raise ValidationError(
            "Custom provider endpoint overrides are not supported by the pinned agentgateway resource translator",
            details=[{"field": "base_url", "issue": "unsupported_in_this_slice"}],
        )
    duplicate = session.scalar(
        select(ModelBackendRecord.id).where(
            ModelBackendRecord.tenant_id == tenant_id,
            ModelBackendRecord.name == request.name,
        )
    )
    if duplicate is not None:
        raise ResourceConflictError(f"Model '{request.name}' already exists in this tenant")

    now = int(time.time())
    row = ModelBackendRecord(
        id=f"model-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        name=request.name,
        provider=request.provider.value,
        model_name=request.model_name,
        secret_ref=request.secret_ref,
        base_url=request.base_url,
        cost_per_1k_input_tokens=request.cost_per_1k_input_tokens,
        cost_per_1k_output_tokens=request.cost_per_1k_output_tokens,
        is_active=request.is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.MODEL_REGISTERED,
        resource_type="model",
        resource_id=row.id,
        details={"name": row.name, "provider": row.provider},
    )
    session.flush()
    return ModelBackend.model_validate(row, from_attributes=True)
