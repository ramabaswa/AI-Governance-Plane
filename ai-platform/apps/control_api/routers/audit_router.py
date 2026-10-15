"""Tenant-scoped tamper-evident audit evidence endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from features.audit_evidence.service import list_events
from features.database import get_db_session
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_permission,
    require_tenant_context,
)
from shared.contracts.audit import AuditEvent

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Evidence Ledger"])


@router.get("/events", response_model=list[AuditEvent])
async def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("audit:read")),
    session: Session = Depends(get_db_session),
):
    """Read the tenant audit chain; this query is itself recorded in that chain."""
    return list_events(session, tenant_id=tenant_id, actor=current_user.subject, limit=limit)
