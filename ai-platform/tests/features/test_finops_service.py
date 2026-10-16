"""Focused unit tests for advisory FinOps semantics."""

import pytest

from features.finops import service
from shared.contracts.finops import BudgetPolicyUpdate
from shared.errors.exceptions import ObservabilityUnavailableError, ValidationError


def test_budget_spend_sums_only_observed_values_and_is_not_a_hard_cap(
    feature_session,
    monkeypatch,
):
    monkeypatch.setenv("PROMETHEUS_QUERY_URL", "https://prometheus.example.test")
    monkeypatch.setenv("PROMETHEUS_ESTIMATED_COST_QUERY", 'sum(cost{tenant="$tenant_id"})')
    monkeypatch.setattr(
        service,
        "query_metrics",
        lambda _tenant_id: {
            "estimated_cost_usd": {
                "available": True,
                "values": [{"value": 2.5}, {"value": 1.25}],
            },
        },
    )

    service.update_budget(
        feature_session,
        tenant_id="tenant-acme",
        actor="admin",
        request=BudgetPolicyUpdate(monthly_budget_usd=25, alert_threshold_pct=75),
    )
    budget = service.get_budget(feature_session, tenant_id="tenant-acme")
    assert budget.current_spend_usd == 3.75
    assert budget.spend_source == "prometheus:tenant-scoped-query"
    assert budget.hard_cap_enforcement == "unavailable"


def test_budget_rejects_nonfinite_or_negative_observed_spend(feature_session, monkeypatch):
    monkeypatch.setenv("PROMETHEUS_QUERY_URL", "https://prometheus.example.test")
    monkeypatch.setenv("PROMETHEUS_ESTIMATED_COST_QUERY", 'sum(cost{tenant="$tenant_id"})')
    monkeypatch.setattr(
        service,
        "query_metrics",
        lambda _tenant_id: {
            "estimated_cost_usd": {
                "available": True,
                "values": [{"value": -1}],
            },
        },
    )
    with pytest.raises(ObservabilityUnavailableError):
        service.get_budget(feature_session, tenant_id="tenant-acme")


def test_hard_cap_request_is_rejected_without_persisting_budget(feature_session):
    with pytest.raises(ValidationError):
        service.update_budget(
            feature_session,
            tenant_id="tenant-acme",
            actor="admin",
            request=BudgetPolicyUpdate(
                monthly_budget_usd=25,
                alert_threshold_pct=80,
                hard_cap_enabled=True,
            ),
        )
    assert service.get_budget(
        feature_session,
        tenant_id="tenant-acme",
        observe_spend=False,
    ).configured is False
