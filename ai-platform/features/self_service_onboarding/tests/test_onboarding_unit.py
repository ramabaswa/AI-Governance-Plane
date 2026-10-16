import pytest

from features.self_service_onboarding import service
from tests.feature_test_support import feature_database
from shared.contracts.onboarding import OnboardingDecision, OnboardingRequestCreate
from shared.errors.exceptions import ForbiddenError


def test_onboarding_reviewer_must_be_distinct_from_requester():
    with feature_database() as session:
        request = service.submit_request(
            session,
            tenant_id="tenant-acme",
            actor="requester",
            request=OnboardingRequestCreate(
                application_name="onboarded-app",
                requested_models=[],
            ),
        )
        with pytest.raises(ForbiddenError):
            service.review_request(
                session,
                tenant_id="tenant-acme",
                request_id=request.id,
                actor="requester",
                decision=OnboardingDecision(decision="approved"),
            )
