"""Version and restore tenant route intent without conflating desired and observed state."""

import hashlib
import json
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.persistence import GatewayRouteRecord, PolicyRevisionRecord
from shared.contracts.audit import AuditAction
from shared.contracts.policy_lifecycle import PolicyRevision
from shared.errors.exceptions import ResourceNotFoundError, ValidationError


def route_snapshot(row: GatewayRouteRecord) -> dict:
    return {
        "name": row.name,
        "path_prefix": row.path_prefix,
        "backend_model_id": row.backend_model_id,
        "failover_model_ids": row.failover_model_ids,
        "traffic_weights": row.traffic_weights,
        "dlp_rules": row.dlp_rules,
        "rate_limit_rpm": row.rate_limit_rpm,
    }


def create_route_revision(
    session: Session,
    *,
    row: GatewayRouteRecord,
    actor: str,
) -> PolicyRevisionRecord:
    snapshot = route_snapshot(row)
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    now = int(time.time())
    revision = PolicyRevisionRecord(
        id=f"policy-rev-{uuid.uuid4().hex[:12]}",
        tenant_id=row.tenant_id,
        resource_type="gateway_route",
        resource_id=row.id,
        revision=row.revision_id,
        state="pending",
        snapshot=snapshot,
        checksum=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        created_by=actor,
        created_at=now,
        updated_at=now,
    )
    session.add(revision)
    append_event(
        session,
        tenant_id=row.tenant_id,
        actor=actor,
        action=AuditAction.POLICY_REVISION_CREATED,
        resource_type="gateway_route",
        resource_id=row.id,
        details={"revision": row.revision_id, "checksum": revision.checksum},
    )
    return revision


def update_route_revision_state(
    session: Session,
    *,
    tenant_id: str,
    route_id: str,
    revision_number: int,
    state: str,
    actor: str,
    details: dict | None = None,
) -> None:
    revision = session.scalar(
        select(PolicyRevisionRecord).where(
            PolicyRevisionRecord.tenant_id == tenant_id,
            PolicyRevisionRecord.resource_id == route_id,
            PolicyRevisionRecord.revision == revision_number,
        )
    )
    if revision is None or revision.state == state:
        return
    previous_state = revision.state
    revision.state = state
    revision.updated_at = int(time.time())
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.POLICY_REVISION_STATE_CHANGED,
        resource_type="gateway_route",
        resource_id=route_id,
        details={
            "revision": revision_number,
            "from": previous_state,
            "to": state,
            **(details or {}),
        },
    )


def list_route_revisions(
    session: Session,
    *,
    tenant_id: str,
    route_id: str,
) -> list[PolicyRevision]:
    route_exists = session.scalar(
        select(GatewayRouteRecord.id).where(
            GatewayRouteRecord.tenant_id == tenant_id,
            GatewayRouteRecord.id == route_id,
        )
    )
    if route_exists is None:
        raise ResourceNotFoundError("Gateway route", route_id)
    rows = session.scalars(
        select(PolicyRevisionRecord)
        .where(
            PolicyRevisionRecord.tenant_id == tenant_id,
            PolicyRevisionRecord.resource_id == route_id,
            PolicyRevisionRecord.resource_type == "gateway_route",
        )
        .order_by(PolicyRevisionRecord.revision.desc())
    ).all()
    return [PolicyRevision.model_validate(row, from_attributes=True) for row in rows]


def prepare_route_rollback(
    session: Session,
    *,
    tenant_id: str,
    route_id: str,
    revision_number: int,
    actor: str,
) -> GatewayRouteRecord:
    route = session.scalar(
        select(GatewayRouteRecord).where(
            GatewayRouteRecord.tenant_id == tenant_id,
            GatewayRouteRecord.id == route_id,
        )
    )
    if route is None:
        raise ResourceNotFoundError("Gateway route", route_id)
    revision = session.scalar(
        select(PolicyRevisionRecord).where(
            PolicyRevisionRecord.tenant_id == tenant_id,
            PolicyRevisionRecord.resource_id == route_id,
            PolicyRevisionRecord.revision == revision_number,
            PolicyRevisionRecord.resource_type == "gateway_route",
        )
    )
    if revision is None:
        raise ResourceNotFoundError("Policy revision", str(revision_number))
    snapshot = revision.snapshot
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    actual_checksum = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    if actual_checksum != revision.checksum:
        raise ValidationError("Policy revision checksum verification failed")
    for field, value in snapshot.items():
        setattr(route, field, value)
    route.lifecycle_state = "draft"
    route.updated_at = int(time.time())
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.POLICY_ROLLED_BACK,
        resource_type="gateway_route",
        resource_id=route_id,
        details={"source_revision": revision_number},
    )
    session.flush()
    return route
