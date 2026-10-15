"""Human-in-the-Loop (HITL) Approvals router."""

from typing import List
from fastapi import APIRouter, Depends, Path
from shared.contracts.policy import (
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalDecisionRequest,
)
from shared.authorization.dependencies import (
    get_current_user,
    require_tenant_context,
    require_permission,
    AuthenticatedUser,
)
from features.state_store import STATE_STORE

router = APIRouter(prefix="/api/v1/approvals", tags=["Policy Approvals"])


@router.get("", response_model=List[ApprovalRequest])
async def list_approvals(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List pending and historical approval requests."""
    return [req for req in STATE_STORE.approvals.values() if req.tenant_id == tenant_id]


@router.post("", status_code=201, response_model=ApprovalRequest)
async def create_approval(
    req: ApprovalRequestCreate,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Submit a policy change for approval."""
    return STATE_STORE.create_approval_request(
        tenant_id=tenant_id,
        policy_type=req.policy_type,
        target_resource_id=req.target_resource_id,
        target_environment=req.target_environment,
        change_summary=req.change_summary,
        proposed_diff=req.proposed_diff,
        requested_by=current_user.subject,
    )


@router.post("/{request_id}/decide", response_model=ApprovalRequest)
async def decide_approval(
    req: ApprovalDecisionRequest,
    request_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("approval:decide")),
):
    """
    Decide an approval request (approve or deny).
    Strict Rule: Self-approval is rejected and committed as 'denied'.
    """
    return STATE_STORE.decide_approval_request(
        tenant_id=tenant_id,
        request_id=request_id,
        decision=req.decision,
        decided_by=current_user.subject,
        comments=req.comments,
    )
