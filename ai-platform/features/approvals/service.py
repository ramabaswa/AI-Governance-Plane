"""Approval request lifecycle with tenant isolation and separation of duties."""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.persistence import ApprovalRequestRecord
from shared.contracts.audit import AuditAction
from shared.contracts.policy import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalRequestCreate,
)
from shared.errors.exceptions import (
    ForbiddenError,
    ResourceNotFoundError,
    ResourceConflictError,
)


def _contract(row: ApprovalRequestRecord) -> ApprovalRequest:
    return ApprovalRequest.model_validate(row, from_attributes=True)


def list_requests(session: Session, tenant_id: str) -> list[ApprovalRequest]:
    rows = session.scalars(
        select(ApprovalRequestRecord)
        .where(ApprovalRequestRecord.tenant_id == tenant_id)
        .order_by(ApprovalRequestRecord.created_at.desc(), ApprovalRequestRecord.id.desc())
    ).all()
    return [_contract(row) for row in rows]


def get_request(session: Session, *, tenant_id: str, request_id: str) -> ApprovalRequestRecord:
    row = session.scalar(
        select(ApprovalRequestRecord).where(
            ApprovalRequestRecord.id == request_id,
            ApprovalRequestRecord.tenant_id == tenant_id,
        ).with_for_update()
    )
    if row is None:
        raise ResourceNotFoundError("Approval request", request_id)
    return row


def create_request(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: ApprovalRequestCreate,
) -> ApprovalRequest:
    now = int(time.time())
    row = ApprovalRequestRecord(
        id=f"approval-{uuid.uuid4().hex[:16]}",
        tenant_id=tenant_id,
        policy_type=request.policy_type,
        target_resource_id=request.target_resource_id,
        target_environment=request.target_environment,
        change_summary=request.change_summary,
        proposed_diff=request.proposed_diff,
        requested_by=actor,
        status="pending",
        created_at=now,
    )
    session.add(row)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.POLICY_APPROVAL_REQUESTED,
        resource_type="approval_request",
        resource_id=row.id,
        details={
            "policy_type": row.policy_type,
            "target_resource_id": row.target_resource_id,
            "target_environment": row.target_environment,
        },
    )
    session.flush()
    return _contract(row)


def decide_request(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
    actor: str,
    decision: ApprovalDecision,
    comments: str | None,
) -> ApprovalRequest:
    row = get_request(session, tenant_id=tenant_id, request_id=request_id)
    if row.status != "pending":
        raise ResourceConflictError("Approval request has already been decided")
    if row.requested_by == actor:
        raise ForbiddenError("Approval requesters cannot approve or deny their own request")

    row.status = decision.value
    row.decided_by = actor
    row.decided_at = int(time.time())
    row.decision_comments = comments
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.POLICY_APPROVAL_DECIDED,
        resource_type="approval_request",
        resource_id=row.id,
        details={"decision": decision.value},
    )
    session.flush()
    return _contract(row)


def consume_approved_request(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
    actor: str,
    policy_type: str,
    target_resource_id: str,
) -> ApprovalRequestRecord:
    row = get_request(session, tenant_id=tenant_id, request_id=request_id)
    if row.status != ApprovalDecision.APPROVED.value:
        raise ForbiddenError("A matching approved request is required")
    if row.applied_at is not None:
        raise ResourceConflictError("Approval request has already been applied")
    if row.policy_type != policy_type or row.target_resource_id != target_resource_id:
        raise ForbiddenError("Approval request does not cover this operation")
    row.applied_at = int(time.time())
    return row
