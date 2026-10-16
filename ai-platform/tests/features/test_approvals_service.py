"""Focused unit tests for approval request state transitions."""

import pytest

from features.approvals import service
from shared.contracts.policy import ApprovalDecision, ApprovalRequestCreate
from shared.errors.exceptions import (
    ForbiddenError,
    ResourceConflictError,
    ResourceNotFoundError,
)


def _request():
    return ApprovalRequestCreate(
        policy_type="application_activation",
        target_resource_id="app-production",
        target_environment="production",
        change_summary="Activate production application",
        proposed_diff="Set lifecycle to active",
    )


def test_approval_decision_enforces_separation_of_duties_and_is_single_use(feature_session):
    request = service.create_request(
        feature_session,
        tenant_id="tenant-acme",
        actor="requester",
        request=_request(),
    )

    with pytest.raises(ForbiddenError):
        service.decide_request(
            feature_session,
            tenant_id="tenant-acme",
            request_id=request.id,
            actor="requester",
            decision=ApprovalDecision.APPROVED,
            comments=None,
        )

    approved = service.decide_request(
        feature_session,
        tenant_id="tenant-acme",
        request_id=request.id,
        actor="reviewer",
        decision=ApprovalDecision.APPROVED,
        comments="Reviewed",
    )
    assert approved.status == "approved"
    assert approved.decided_by == "reviewer"

    consumed = service.consume_approved_request(
        feature_session,
        tenant_id="tenant-acme",
        request_id=request.id,
        actor="operator",
        policy_type="application_activation",
        target_resource_id="app-production",
    )
    assert consumed.applied_at is not None
    with pytest.raises(ResourceConflictError):
        service.consume_approved_request(
            feature_session,
            tenant_id="tenant-acme",
            request_id=request.id,
            actor="operator",
            policy_type="application_activation",
            target_resource_id="app-production",
        )


def test_approval_is_bound_to_tenant_type_and_resource(feature_session):
    request = service.create_request(
        feature_session,
        tenant_id="tenant-acme",
        actor="requester",
        request=_request(),
    )
    service.decide_request(
        feature_session,
        tenant_id="tenant-acme",
        request_id=request.id,
        actor="reviewer",
        decision=ApprovalDecision.APPROVED,
        comments=None,
    )

    with pytest.raises(ResourceNotFoundError):
        service.consume_approved_request(
            feature_session,
            tenant_id="tenant-globex",
            request_id=request.id,
            actor="operator",
            policy_type="application_activation",
            target_resource_id="app-production",
        )
    with pytest.raises(ForbiddenError):
        service.consume_approved_request(
            feature_session,
            tenant_id="tenant-acme",
            request_id=request.id,
            actor="operator",
            policy_type="policy_change",
            target_resource_id="app-production",
        )
