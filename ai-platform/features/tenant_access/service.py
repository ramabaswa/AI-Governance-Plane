"""Durable tenant and membership operations."""

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.persistence import TenantMembershipRecord, TenantRecord
from shared.authorization.roles import Role
from shared.contracts.audit import AuditAction
from shared.contracts.tenant import (
    Tenant,
    TenantCreate,
    TenantMembership,
    TenantMembershipCreate,
)
from shared.errors.exceptions import ResourceConflictError, ResourceNotFoundError, ValidationError


def list_tenants(session: Session, *, tenant_id: str, platform_admin: bool) -> list[Tenant]:
    query = select(TenantRecord).where(TenantRecord.is_active.is_(True))
    if not platform_admin:
        query = query.where(TenantRecord.id == tenant_id)
    rows = session.scalars(query.order_by(TenantRecord.name)).all()
    return [Tenant.model_validate(row, from_attributes=True) for row in rows]


def create_tenant(
    session: Session,
    *,
    actor: str,
    request: TenantCreate,
) -> Tenant:
    duplicate = session.scalar(
        select(TenantRecord.id).where(TenantRecord.slug == request.slug)
    )
    if duplicate is not None:
        raise ResourceConflictError(f"Tenant slug '{request.slug}' is already registered")
    now = int(time.time())
    row = TenantRecord(
        id=f"tenant-{request.slug}",
        name=request.name,
        slug=request.slug,
        description=request.description,
        created_at=now,
        updated_at=now,
        is_active=True,
    )
    session.add(row)
    append_event(
        session,
        tenant_id="platform",
        actor=actor,
        action=AuditAction.TENANT_CREATED,
        resource_type="tenant",
        resource_id=row.id,
        details={"slug": row.slug, "name": row.name},
    )
    session.flush()
    return Tenant.model_validate(row, from_attributes=True)


def create_membership(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: TenantMembershipCreate,
) -> TenantMembership:
    tenant = session.scalar(
        select(TenantRecord).where(
            TenantRecord.id == tenant_id,
            TenantRecord.is_active.is_(True),
        )
    )
    if tenant is None:
        raise ResourceNotFoundError("Tenant", tenant_id)
    _validate_membership_roles(tenant_id, request.roles)
    existing = session.scalar(
        select(TenantMembershipRecord).where(
            TenantMembershipRecord.tenant_id == tenant_id,
            TenantMembershipRecord.subject == request.subject,
        )
    )
    if existing is not None:
        raise ResourceConflictError("Subject already has a membership in this tenant")
    row = TenantMembershipRecord(
        tenant_id=tenant_id,
        subject=request.subject,
        roles=[role.value for role in request.roles],
        created_at=int(time.time()),
    )
    session.add(row)
    append_event(
        session,
        tenant_id="platform",
        actor=actor,
        action=AuditAction.MEMBERSHIP_CREATED,
        resource_type="tenant_membership",
        resource_id=f"{tenant_id}:{request.subject}",
        details={"roles": [role.value for role in request.roles]},
    )
    session.flush()
    return TenantMembership.model_validate(row, from_attributes=True)


def list_memberships(session: Session, tenant_id: str) -> list[TenantMembership]:
    rows = session.scalars(
        select(TenantMembershipRecord)
        .where(TenantMembershipRecord.tenant_id == tenant_id)
        .order_by(TenantMembershipRecord.subject)
    ).all()
    return [TenantMembership.model_validate(row, from_attributes=True) for row in rows]


def update_membership(
    session: Session,
    *,
    tenant_id: str,
    subject: str,
    actor: str,
    request: TenantMembershipCreate,
) -> TenantMembership:
    row = session.scalar(
        select(TenantMembershipRecord).where(
            TenantMembershipRecord.tenant_id == tenant_id,
            TenantMembershipRecord.subject == subject,
        )
    )
    if row is None:
        raise ResourceNotFoundError("Tenant membership", f"{tenant_id}:{subject}")
    if request.subject != subject:
        raise ValidationError("Membership subject in the request must match the URL")
    _validate_membership_roles(tenant_id, request.roles)
    old_roles = set(row.roles)
    new_roles = {role.value for role in request.roles}
    if (
        tenant_id == "platform"
        and Role.PLATFORM_ADMIN.value in old_roles
        and Role.PLATFORM_ADMIN.value not in new_roles
    ):
        admins = session.scalars(
            select(TenantMembershipRecord).where(TenantMembershipRecord.tenant_id == "platform")
        ).all()
        if sum(Role.PLATFORM_ADMIN.value in member.roles for member in admins) <= 1:
            raise ValidationError("The final platform administrator cannot be removed")
    row.roles = sorted(new_roles)
    append_event(
        session,
        tenant_id="platform",
        actor=actor,
        action=AuditAction.MEMBERSHIP_UPDATED,
        resource_type="tenant_membership",
        resource_id=f"{tenant_id}:{subject}",
        details={"from": sorted(old_roles), "to": sorted(new_roles)},
    )
    session.flush()
    return TenantMembership.model_validate(row, from_attributes=True)


def _validate_membership_roles(tenant_id: str, roles: list[Role]) -> None:
    if tenant_id == "platform":
        if roles != [Role.PLATFORM_ADMIN]:
            raise ValidationError("The platform tenant accepts only platform_admin memberships")
    elif Role.PLATFORM_ADMIN in roles:
        raise ValidationError("platform_admin cannot be assigned as a tenant-scoped role")
