"""Tenant budget intent and observed spend reporting."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from features.database import get_db_session
from features.finops import service
from shared.authorization.dependencies import (
    AuthenticatedUser,
    require_permission,
    require_tenant_context,
)
from shared.contracts.finops import BudgetPolicyUpdate, BudgetPolicyView

router = APIRouter(prefix="/api/v1/finops", tags=["FinOps & Budgets"])


@router.get("/budgets", response_model=BudgetPolicyView)
async def get_budget(
    tenant_id: str = Depends(require_tenant_context),
    _user: AuthenticatedUser = Depends(require_permission("finops:read")),
    session: Session = Depends(get_db_session),
):
    return service.get_budget(session, tenant_id=tenant_id)


@router.put("/budgets", response_model=BudgetPolicyView)
async def update_budget(
    request: BudgetPolicyUpdate,
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("finops:update")),
    session: Session = Depends(get_db_session),
):
    service.update_budget(
        session,
        tenant_id=tenant_id,
        actor=user.subject,
        request=request,
    )
    session.flush()
    return service.get_budget(session, tenant_id=tenant_id, observe_spend=False)
