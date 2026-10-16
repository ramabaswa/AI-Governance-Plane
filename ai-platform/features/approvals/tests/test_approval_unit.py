import pytest

from features.approvals import service
from tests.feature_test_support import feature_database
from shared.contracts.policy import ApprovalDecision, ApprovalRequestCreate
from shared.errors.exceptions import ForbiddenError


def test_requester_cannot_approve_own_request():
    with feature_database() as session:
        request = service.create_request(
            session,
            tenant_id="tenant-acme",
            actor="requester",
            request=ApprovalRequestCreate(
                policy_type="application_activation",
                target_resource_id="app-prod",
                target_environment="production",
                change_summary="Activate",
                proposed_diff="lifecycle_state: active",
            ),
        )
        with pytest.raises(ForbiddenError):
            service.decide_request(
                session,
                tenant_id="tenant-acme",
                request_id=request.id,
                actor="requester",
                decision=ApprovalDecision.APPROVED,
                comments=None,
            )
