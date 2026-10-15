"""Contracts for Tenants and Tenant Membership."""

from typing import List, Optional
from pydantic import BaseModel, Field
from shared.authorization.roles import Role


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    slug: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None


class Tenant(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    created_at: int
    updated_at: int
    is_active: bool = True


class TenantMember(BaseModel):
    user_id: str
    email: str
    tenant_id: str
    roles: List[Role]
    created_at: int


class TenantMembershipCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    roles: List[Role] = Field(..., min_length=1)


class TenantMembership(BaseModel):
    subject: str
    tenant_id: str
    roles: List[Role]
    created_at: int
