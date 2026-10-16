"""Persist budget intent and report only spend observed from Prometheus."""

import math
import os
import time

from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.observability.service import query_metrics
from features.persistence import BudgetPolicyRecord
from shared.contracts.audit import AuditAction
from shared.contracts.finops import BudgetPolicyUpdate, BudgetPolicyView
from shared.errors.exceptions import ObservabilityUnavailableError, ValidationError


def update_budget(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: BudgetPolicyUpdate,
) -> BudgetPolicyRecord:
    if request.hard_cap_enabled:
        raise ValidationError(
            "Hard-cap enforcement is not available through the configured OSS gateway path"
        )
    row = session.get(BudgetPolicyRecord, tenant_id)
    now = int(time.time())
    if row is None:
        row = BudgetPolicyRecord(
            tenant_id=tenant_id,
            monthly_budget_usd=request.monthly_budget_usd,
            alert_threshold_pct=request.alert_threshold_pct,
            updated_by=actor,
            updated_at=now,
        )
        session.add(row)
    else:
        row.monthly_budget_usd = request.monthly_budget_usd
        row.alert_threshold_pct = request.alert_threshold_pct
        row.updated_by = actor
        row.updated_at = now
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.BUDGET_POLICY_UPDATED,
        resource_type="budget_policy",
        resource_id=tenant_id,
        details={
            "monthly_budget_usd": row.monthly_budget_usd,
            "alert_threshold_pct": row.alert_threshold_pct,
        },
    )
    session.flush()
    return row


def get_budget(
    session: Session,
    *,
    tenant_id: str,
    observe_spend: bool = True,
) -> BudgetPolicyView:
    row = session.get(BudgetPolicyRecord, tenant_id)
    spend, source = (
        _observed_spend(tenant_id)
        if observe_spend
        else (None, "not_queried")
    )
    if row is None:
        return BudgetPolicyView(
            tenant_id=tenant_id,
            configured=False,
            monthly_budget_usd=0,
            alert_threshold_pct=80,
            updated_by="",
            updated_at=0,
            current_spend_usd=spend,
            spend_source=source,
            hard_cap_enforcement="unavailable",
        )
    return BudgetPolicyView(
        tenant_id=tenant_id,
        configured=True,
        monthly_budget_usd=row.monthly_budget_usd,
        alert_threshold_pct=row.alert_threshold_pct,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        current_spend_usd=spend,
        spend_source=source,
        hard_cap_enforcement="unavailable",
    )


def _observed_spend(tenant_id: str) -> tuple[float | None, str]:
    if not os.getenv("PROMETHEUS_QUERY_URL"):
        return None, "unavailable: PROMETHEUS_QUERY_URL is not configured"
    if not os.getenv("PROMETHEUS_ESTIMATED_COST_QUERY"):
        return None, "unavailable: no tenant-scoped cost query configured"
    metrics = query_metrics(tenant_id)
    metric = metrics.get("estimated_cost_usd", {})
    if not metric.get("available"):
        return None, "unavailable: cost metric not configured"
    values = metric.get("values")
    if not isinstance(values, list):
        return None, "unavailable: malformed cost metric"
    if not values:
        return None, "unavailable: cost query returned no series"
    observed = [item.get("value") for item in values if isinstance(item, dict)]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in observed):
        raise ObservabilityUnavailableError("Prometheus", "estimated cost query returned an invalid value")
    return sum(observed), "prometheus:tenant-scoped-query"
