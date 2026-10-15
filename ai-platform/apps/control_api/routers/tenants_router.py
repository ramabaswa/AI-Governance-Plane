"""Tenant and persisted identity-membership administration endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from features.database import get_db_session
from features.tenant_access import service
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from shared.authorization.roles import Role
from shared.contracts.tenant import (
    Tenant,
    TenantCreate,
    TenantMembership,
    TenantMembershipCreate,
)

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenant Management"])


@router.get("", response_model=List[Tenant])
async def list_tenants(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    return service.list_tenants(
        session,
        tenant_id=current_user.tenant_id,
        platform_admin=Role.PLATFORM_ADMIN in current_user.roles,
    )


@router.post("", status_code=201, response_model=Tenant)
async def create_tenant(
    req: TenantCreate,
    current_user: AuthenticatedUser = Depends(require_role([Role.PLATFORM_ADMIN])),
    session: Session = Depends(get_db_session),
):
    return service.create_tenant(session, actor=current_user.subject, request=req)


@router.get("/{tenant_id}/memberships", response_model=List[TenantMembership])
async def list_tenant_memberships(
    tenant_id: str = Path(...),
    current_user: AuthenticatedUser = Depends(require_role([Role.PLATFORM_ADMIN])),
    session: Session = Depends(get_db_session),
):
    return service.list_memberships(session, tenant_id)


@router.post("/{tenant_id}/memberships", status_code=201, response_model=TenantMembership)
async def create_tenant_membership(
    req: TenantMembershipCreate,
    tenant_id: str = Path(...),
    current_user: AuthenticatedUser = Depends(require_role([Role.PLATFORM_ADMIN])),
    session: Session = Depends(get_db_session),
):
    """Map an OIDC subject to tenant-local roles; token role claims are not trusted."""
    return service.create_membership(
        session,
        tenant_id=tenant_id,
        actor=current_user.subject,
        request=req,
    )


@router.put("/{tenant_id}/memberships/{subject}", response_model=TenantMembership)
async def update_tenant_membership(
    req: TenantMembershipCreate,
    tenant_id: str = Path(...),
    subject: str = Path(...),
    current_user: AuthenticatedUser = Depends(require_role([Role.PLATFORM_ADMIN])),
    session: Session = Depends(get_db_session),
):
    return service.update_membership(
        session,
        tenant_id=tenant_id,
        subject=subject,
        actor=current_user.subject,
        request=req,
    )
