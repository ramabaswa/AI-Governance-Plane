"""Focused unit tests for onboarding review and completion rules."""

import pytest

from features.self_service_onboarding import service
from shared.contracts.onboarding import OnboardingDecision, OnboardingRequestCreate
from shared.errors.exceptions import ForbiddenError, ResourceConflictError


def _request(environment="development"):
    return OnboardingRequestCreate(
        application_name="onboarded-test-app",
        environment=environment,
        requested_models=[],
        monthly_token_quota=50_000,
    )


def test_onboarding_requester_cannot_review_or_complete_before_approval(feature_session):
    request = service.submit_request(
        feature_session,
        tenant_id="tenant-acme",
        actor="requester",
        request=_request(),
    )

    with pytest.raises(ForbiddenError):
        service.review_request(
            feature_session,
            tenant_id="tenant-acme",
            request_id=request.id,
            actor="requester",
            decision=OnboardingDecision(decision="approved"),
        )
    with pytest.raises(ResourceConflictError):
        service.complete_request(
            feature_session,
            tenant_id="tenant-acme",
            request_id=request.id,
            actor="requester",
            kubernetes_client=object(),
        )


def test_onboarding_listing_hides_other_requesters_from_non_reviewers(feature_session):
    service.submit_request(
        feature_session,
        tenant_id="tenant-acme",
        actor="alice",
        request=_request(),
    )
    service.submit_request(
        feature_session,
        tenant_id="tenant-acme",
        actor="bob",
        request=OnboardingRequestCreate(
            application_name="bob-app",
            requested_models=[],
        ),
    )

    own = service.list_requests(
        feature_session,
        tenant_id="tenant-acme",
        actor="alice",
        reviewer=False,
    )
    reviewer = service.list_requests(
        feature_session,
        tenant_id="tenant-acme",
        actor="alice",
        reviewer=True,
    )
    assert [item.requested_by for item in own] == ["alice"]
    assert {item.requested_by for item in reviewer} == {"alice", "bob"}
