"""FastAPI dependencies for OIDC identity and persisted tenant authorization."""

import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from opentelemetry import trace

from features.database import get_db_session
from features.persistence import TenantMembershipRecord, TenantRecord
from shared.authorization.jwt_handler import decode_access_token, verify_oidc_token
from shared.authorization.roles import Role, has_permission
from shared.errors.exceptions import ForbiddenError, UnauthorizedError, ValidationError


class AuthenticatedUser:
    def __init__(self, subject: str, tenant_id: str, roles: List[Role], raw_claims: Dict[str, Any]):
        self.subject = subject
        self.tenant_id = tenant_id
        self.roles = roles
        self.raw_claims = raw_claims

    def has_role(self, role: Role) -> bool:
        return role in self.roles or Role.PLATFORM_ADMIN in self.roles

    def has_perm(self, permission: str) -> bool:
        return any(has_permission(role, permission) for role in self.roles)


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    requested_tenant_header: Optional[str] = Header(None, alias="X-Tenant-ID"),
    session: Session = Depends(get_db_session),
) -> AuthenticatedUser:
    """Verify the bearer token and resolve all authority from database membership."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedError("Missing bearer token")

    if os.getenv("ENVIRONMENT", "").strip().lower() in {"development", "test"}:
        claims = decode_access_token(token)
    else:
        claims = verify_oidc_token(token)

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise UnauthorizedError("Token is missing a valid 'sub' claim")

    memberships = session.scalars(
        select(TenantMembershipRecord)
        .join(TenantRecord, TenantRecord.id == TenantMembershipRecord.tenant_id)
        .where(
            TenantMembershipRecord.subject == subject,
            TenantRecord.is_active.is_(True),
        )
    ).all()
    roles_by_tenant: dict[str, list[Role]] = {}
    for membership in memberships:
        try:
            roles_by_tenant[membership.tenant_id] = [Role(role) for role in membership.roles]
        except ValueError as error:
            raise UnauthorizedError("Stored tenant membership contains an invalid role") from error

    platform_admin = Role.PLATFORM_ADMIN in roles_by_tenant.get("platform", [])
    if requested_tenant_header:
        if platform_admin:
            tenant_exists = session.scalar(
                select(TenantRecord.id).where(
                    TenantRecord.id == requested_tenant_header,
                    TenantRecord.is_active.is_(True),
                )
            )
            if requested_tenant_header != "platform" and tenant_exists is None:
                raise ForbiddenError("Requested tenant is unavailable")
            tenant_id = requested_tenant_header
            roles = [Role.PLATFORM_ADMIN, *roles_by_tenant.get(tenant_id, [])]
        else:
            roles = roles_by_tenant.get(requested_tenant_header)
            if roles is None:
                raise ForbiddenError("Caller has no membership in the requested tenant")
            tenant_id = requested_tenant_header
    elif platform_admin:
        tenant_id = "platform"
        roles = [Role.PLATFORM_ADMIN]
    elif len(roles_by_tenant) == 1:
        tenant_id, roles = next(iter(roles_by_tenant.items()))
    elif len(roles_by_tenant) > 1:
        raise ValidationError("X-Tenant-ID is required when the caller belongs to multiple tenants")
    else:
        raise ForbiddenError("Caller has no active tenant membership")

    trace.get_current_span().set_attribute("tenant.id", tenant_id)
    request.state.tenant_id = tenant_id
    return AuthenticatedUser(
        subject=subject,
        tenant_id=tenant_id,
        roles=roles,
        raw_claims={"iss": claims.get("iss"), "sub": subject},
    )


def require_tenant_context(
    current_user: AuthenticatedUser = Depends(get_current_user),
    requested_tenant_header: Optional[str] = Header(None, alias="X-Tenant-ID"),
) -> str:
    """Return the tenant already resolved and authorized during identity resolution."""
    if requested_tenant_header and requested_tenant_header != current_user.tenant_id:
        raise ForbiddenError("Tenant context could not be resolved from persisted membership")
    return current_user.tenant_id


def require_role(allowed_roles: List[Role]):
    """Enforce that the caller holds at least one of the allowed roles."""
    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if Role.PLATFORM_ADMIN in user.roles:
            return user
        if any(role in user.roles for role in allowed_roles):
            return user
        raise ForbiddenError(f"Operation requires one of roles: {[role.value for role in allowed_roles]}")
    return dependency


def require_permission(permission: str):
    """Enforce that persisted tenant roles grant the requested permission."""
    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.has_perm(permission):
            return user
        raise ForbiddenError(f"Caller lacks required permission: '{permission}'")
    return dependency
