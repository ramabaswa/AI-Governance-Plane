"""Durable route intent and observed Kubernetes status."""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.application_agent_registry.service import (
    finalize_pending_revocations,
    tenant_api_key_configmap,
)
from features.guardrails.service import validate_prompt_guard_rules
from features.persistence import GatewayRouteRecord, ModelBackendRecord
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.contracts.audit import AuditAction
from shared.contracts.model import ModelBackend
from shared.contracts.route import GatewayRoute, GatewayRouteCreate
from shared.errors.exceptions import ResourceConflictError, ResourceNotFoundError, ValidationError
from shared.validation.route_validator import validate_path_prefix, validate_traffic_weights


def list_routes(session: Session, tenant_id: str) -> list[GatewayRoute]:
    rows = session.scalars(
        select(GatewayRouteRecord)
        .where(GatewayRouteRecord.tenant_id == tenant_id)
        .order_by(GatewayRouteRecord.created_at.desc())
    ).all()
    return [GatewayRoute.model_validate(row, from_attributes=True) for row in rows]


def get_route(session: Session, tenant_id: str, route_id: str) -> GatewayRoute:
    row = session.scalar(
        select(GatewayRouteRecord).where(
            GatewayRouteRecord.id == route_id,
            GatewayRouteRecord.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ResourceNotFoundError("Gateway route", route_id)
    return GatewayRoute.model_validate(row, from_attributes=True)


def create_route(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: GatewayRouteCreate,
) -> GatewayRoute:
    duplicate = session.scalar(
        select(GatewayRouteRecord.id).where(
            GatewayRouteRecord.tenant_id == tenant_id,
            GatewayRouteRecord.name == request.name,
        )
    )
    if duplicate is not None:
        raise ResourceConflictError(f"Route '{request.name}' already exists in this tenant")
    if request.failover_model_ids:
        raise ValidationError("Failover routing is not supported by this implementation slice")
    if request.rate_limit_rpm is not None:
        raise ValidationError("Route-level rate limiting is not supported by this implementation slice")

    validate_path_prefix(request.path_prefix)
    primary = session.scalar(
        select(ModelBackendRecord).where(
            ModelBackendRecord.id == request.backend_model_id,
            ModelBackendRecord.tenant_id == tenant_id,
            ModelBackendRecord.is_active.is_(True),
        )
    )
    if primary is None:
        raise ResourceNotFoundError("Active tenant model", request.backend_model_id)

    weights = request.traffic_weights or {request.backend_model_id: 100}
    validate_traffic_weights(weights)
    if request.backend_model_id not in weights:
        raise ValidationError("Traffic weights must include the primary backend model")
    models = session.scalars(
        select(ModelBackendRecord).where(
            ModelBackendRecord.tenant_id == tenant_id,
            ModelBackendRecord.id.in_(weights.keys()),
            ModelBackendRecord.is_active.is_(True),
        )
    ).all()
    approved_model_ids = {model.id for model in models}
    unknown = sorted(set(weights) - approved_model_ids)
    if unknown:
        raise ValidationError(
            "Traffic weights reference inactive or unapproved tenant models",
            details=[{"field": "traffic_weights", "unknown_model_ids": unknown}],
        )

    validate_prompt_guard_rules(request.dlp_rules)

    now = int(time.time())
    route_id = f"route-{uuid.uuid4().hex[:12]}"
    row = GatewayRouteRecord(
        id=route_id,
        tenant_id=tenant_id,
        name=request.name,
        path_prefix=request.path_prefix,
        backend_model_id=request.backend_model_id,
        failover_model_ids=[],
        traffic_weights=weights,
        dlp_rules=[rule.model_dump(mode="json") for rule in request.dlp_rules],
        rate_limit_rpm=None,
        revision_id=1,
        lifecycle_state="draft",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.ROUTE_CREATED,
        resource_type="gateway_route",
        resource_id=route_id,
        details={"name": request.name, "path_prefix": request.path_prefix},
    )
    session.flush()
    return GatewayRoute.model_validate(row, from_attributes=True)


def apply_route(
    session: Session,
    *,
    tenant_id: str,
    route_id: str,
    actor: str,
    reconciler: AgentgatewayReconciler | None = None,
) -> dict:
    row = session.scalar(
        select(GatewayRouteRecord).where(
            GatewayRouteRecord.id == route_id,
            GatewayRouteRecord.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ResourceNotFoundError("Gateway route", route_id)

    model_rows = session.scalars(
        select(ModelBackendRecord).where(
            ModelBackendRecord.tenant_id == tenant_id,
            ModelBackendRecord.is_active.is_(True),
        )
    ).all()
    models = {model.id: ModelBackend.model_validate(model, from_attributes=True) for model in model_rows}
    row.lifecycle_state = "pending"
    row.updated_at = int(time.time())
    row.revision_id += 1
    route = GatewayRoute.model_validate(row, from_attributes=True)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.ROUTE_APPLY_REQUESTED,
        resource_type="gateway_route",
        resource_id=route_id,
        details={"revision_id": row.revision_id, "state": "pending"},
    )
    session.flush()
    session.commit()
    active_reconciler = reconciler or AgentgatewayReconciler()
    active_reconciler.apply(
        [route],
        models,
        additional_resources=[tenant_api_key_configmap(session, tenant_id=tenant_id)],
    )
    finalize_pending_revocations(session, tenant_id)
    session.commit()
    return get_route_status(
        session,
        tenant_id=tenant_id,
        route_id=route_id,
        reconciler=active_reconciler,
    )


def get_route_status(
    session: Session,
    *,
    tenant_id: str,
    route_id: str,
    reconciler: AgentgatewayReconciler | None = None,
) -> dict:
    row = session.scalar(
        select(GatewayRouteRecord).where(
            GatewayRouteRecord.id == route_id,
            GatewayRouteRecord.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ResourceNotFoundError("Gateway route", route_id)
    route = GatewayRoute.model_validate(row, from_attributes=True)
    model_rows = session.scalars(
        select(ModelBackendRecord).where(
            ModelBackendRecord.tenant_id == tenant_id,
            ModelBackendRecord.is_active.is_(True),
        )
    ).all()
    models = {model.id: ModelBackend.model_validate(model, from_attributes=True) for model in model_rows}
    status = (reconciler or AgentgatewayReconciler()).read_status(route, models)
    if row.lifecycle_state != status["state"]:
        previous_state = row.lifecycle_state
        row.lifecycle_state = status["state"]
        row.updated_at = int(time.time())
        append_event(
            session,
            tenant_id=tenant_id,
            actor="agentgateway-controller-status",
            action=(
                AuditAction.ROUTE_OBSERVED_ACTIVE
                if status["observed_active"]
                else AuditAction.ROUTE_STATUS_CHANGED
            ),
            resource_type="gateway_route",
            resource_id=route_id,
            details={
                "from": previous_state,
                "to": status["state"],
                "resources": status["resources"],
            },
        )
        session.flush()
    return {"route_id": route_id, **status}
