import pytest

from features.finops import service
from tests.feature_test_support import feature_database
from shared.contracts.finops import BudgetPolicyUpdate
from shared.errors.exceptions import ValidationError


def test_budget_is_advisory_and_hard_cap_is_rejected():
    with feature_database() as session:
        view = service.get_budget(session, tenant_id="tenant-acme", observe_spend=False)
        assert view.configured is False
        assert view.hard_cap_enforcement == "unavailable"

        with pytest.raises(ValidationError, match="Hard-cap enforcement"):
            service.update_budget(
                session,
                tenant_id="tenant-acme",
                actor="admin",
                request=BudgetPolicyUpdate(
                    monthly_budget_usd=100,
                    hard_cap_enabled=True,
                ),
            )
