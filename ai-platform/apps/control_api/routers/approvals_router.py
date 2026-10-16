"""Durable tenant-scoped approval requests."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from features.approvals import service
from features.database import get_db_session
from shared.authorization.dependencies import (
    AuthenticatedUser,
    require_permission,
    require_tenant_context,
)
from shared.contracts.policy import (
    ApprovalDecisionRequest,
    ApprovalRequest,
    ApprovalRequestCreate,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["Policy Approvals"])


@router.get("", response_model=list[ApprovalRequest])
async def list_approvals(
    tenant_id: str = Depends(require_tenant_context),
    _user: AuthenticatedUser = Depends(require_permission("approval:read")),
    session: Session = Depends(get_db_session),
):
    return service.list_requests(session, tenant_id)


@router.post("", status_code=201, response_model=ApprovalRequest)
async def create_approval(
    request: ApprovalRequestCreate,
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("approval:create")),
    session: Session = Depends(get_db_session),
):
    return service.create_request(
        session,
        tenant_id=tenant_id,
        actor=user.subject,
        request=request,
    )


@router.post("/{request_id}/decide", response_model=ApprovalRequest)
async def decide_approval(
    request: ApprovalDecisionRequest,
    request_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("approval:decide")),
    session: Session = Depends(get_db_session),
):
    return service.decide_request(
        session,
        tenant_id=tenant_id,
        request_id=request_id,
        actor=user.subject,
        decision=request.decision,
        comments=request.comments,
    )
