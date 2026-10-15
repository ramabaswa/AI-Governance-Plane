"""FinOps and Budget Management router."""

import time
from fastapi import APIRouter, Depends
from shared.contracts.telemetry import BudgetPolicy
from shared.authorization.dependencies import (
    get_current_user,
    require_tenant_context,
    require_permission,
    AuthenticatedUser,
)
from shared.contracts.audit import AuditAction
from features.state_store import STATE_STORE

router = APIRouter(prefix="/api/v1/finops", tags=["FinOps & Budgets"])


@router.get("/budgets", response_model=BudgetPolicy)
async def get_budget(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get tenant budget policy."""
    b = STATE_STORE.budgets.get(tenant_id)
    if not b:
        now = int(time.time())
        b = BudgetPolicy(
            tenant_id=tenant_id,
            monthly_budget_usd=100.0,
            alert_threshold_pct=80,
            current_spend_usd=0.0,
            hard_cap_enabled=True,
            hard_cap_action="reject_429",
            updated_at=now,
        )
        STATE_STORE.budgets[tenant_id] = b
    return b


@router.put("/budgets", response_model=BudgetPolicy)
async def update_budget(
    req: BudgetPolicy,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("tenant:update")),
):
    """Update tenant budget policy and hard cap thresholds."""
    req.tenant_id = tenant_id
    req.updated_at = int(time.time())
    STATE_STORE.budgets[tenant_id] = req

    STATE_STORE.record_audit_event(
        tenant_id=tenant_id,
        actor=current_user.subject,
        action=AuditAction.AUDIT_READ, # or budget updated
        resource_type="budget",
        resource_id=tenant_id,
        details={"monthly_budget_usd": req.monthly_budget_usd},
    )
    return req
