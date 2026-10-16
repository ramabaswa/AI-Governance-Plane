"""Durable onboarding request, review, and applicant-completion workflow."""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.application_agent_registry.service import create_application
from features.audit_evidence.service import append_event
from features.persistence import ApplicationRecord, OnboardingRequestRecord
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from shared.contracts.application import ApplicationCreate
from shared.contracts.audit import AuditAction
from shared.contracts.onboarding import (
    OnboardingDecision,
    OnboardingRequest,
    OnboardingRequestCreate,
)
from shared.errors.exceptions import (
    ForbiddenError,
    ResourceConflictError,
    ResourceNotFoundError,
)


def _contract(row: OnboardingRequestRecord) -> OnboardingRequest:
    data = row.request_data
    return OnboardingRequest(
        id=row.id,
        tenant_id=row.tenant_id,
        requested_by=row.requested_by,
        application_name=data["application_name"],
        environment=data["environment"],
        requested_models=data["requested_models"],
        monthly_token_quota=data["monthly_token_quota"],
        status=row.status,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_comments=row.review_comments,
        application_id=row.application_id,
        created_at=row.created_at,
    )


def list_requests(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    reviewer: bool,
) -> list[OnboardingRequest]:
    query = select(OnboardingRequestRecord).where(OnboardingRequestRecord.tenant_id == tenant_id)
    if not reviewer:
        query = query.where(OnboardingRequestRecord.requested_by == actor)
    rows = session.scalars(query.order_by(OnboardingRequestRecord.created_at.desc())).all()
    return [_contract(row) for row in rows]


def get_request(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
) -> OnboardingRequestRecord:
    row = session.scalar(
        select(OnboardingRequestRecord).where(
            OnboardingRequestRecord.id == request_id,
            OnboardingRequestRecord.tenant_id == tenant_id,
        ).with_for_update()
    )
    if row is None:
        raise ResourceNotFoundError("Onboarding request", request_id)
    return row


def submit_request(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: OnboardingRequestCreate,
) -> OnboardingRequest:
    now = int(time.time())
    row = OnboardingRequestRecord(
        id=f"onboard-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        requested_by=actor,
        request_data=request.model_dump(mode="json"),
        status="pending",
        created_at=now,
    )
    session.add(row)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.ONBOARDING_REQUESTED,
        resource_type="onboarding_request",
        resource_id=row.id,
        details={"application_name": request.application_name, "environment": request.environment},
    )
    session.flush()
    return _contract(row)


def review_request(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
    actor: str,
    decision: OnboardingDecision,
) -> OnboardingRequest:
    row = get_request(session, tenant_id=tenant_id, request_id=request_id)
    if row.requested_by == actor:
        raise ForbiddenError("Onboarding requesters cannot review their own requests")
    if row.status != "pending":
        raise ResourceConflictError("Onboarding request has already been reviewed")
    row.status = decision.decision
    row.reviewed_by = actor
    row.reviewed_at = int(time.time())
    row.review_comments = decision.comments
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.ONBOARDING_DECIDED,
        resource_type="onboarding_request",
        resource_id=row.id,
        details={"decision": row.status},
    )
    session.flush()
    return _contract(row)


def complete_request(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
    actor: str,
    kubernetes_client: AgentgatewayKubernetesClient,
) -> tuple[OnboardingRequest, str | None]:
    row = get_request(session, tenant_id=tenant_id, request_id=request_id)
    if row.requested_by != actor:
        raise ForbiddenError("Only the onboarding requester can complete this request")
    if row.status != "approved":
        raise ResourceConflictError("Onboarding request must be approved before completion")
    if row.application_id is not None:
        raise ResourceConflictError("Onboarding request has already created its application")
    data = row.request_data
    expected_description = f"Self-service onboarding request {row.id}"
    existing_application = session.scalar(
        select(ApplicationRecord).where(
            ApplicationRecord.tenant_id == tenant_id,
            ApplicationRecord.name == data["application_name"],
        )
    )
    if existing_application is not None:
        if (
            existing_application.created_by != actor
            or existing_application.description != expected_description
        ):
            raise ResourceConflictError("An application with the requested name already exists")
        row.application_id = existing_application.id
        row.status = "completed"
        row.completed_at = int(time.time())
        append_event(
            session,
            tenant_id=tenant_id,
            actor=actor,
            action=AuditAction.ONBOARDING_COMPLETED,
            resource_type="onboarding_request",
            resource_id=row.id,
            details={"application_id": existing_application.id, "credential_recovery": "not_available"},
        )
        session.flush()
        return _contract(row), None
    application, raw_key = create_application(
        session,
        tenant_id=tenant_id,
        created_by=actor,
        request=ApplicationCreate(
            name=data["application_name"],
            description=expected_description,
            environment=data["environment"],
            allowed_models=data["requested_models"],
            monthly_token_quota=data["monthly_token_quota"],
        ),
        kubernetes_client=kubernetes_client,
    )
    row.application_id = application.id
    row.status = "completed"
    row.completed_at = int(time.time())
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.ONBOARDING_COMPLETED,
        resource_type="onboarding_request",
        resource_id=row.id,
        details={"application_id": application.id},
    )
    session.flush()
    return _contract(row), raw_key
