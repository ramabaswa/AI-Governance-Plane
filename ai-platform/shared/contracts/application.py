"""Contracts for Applications, Autonomous Agents, and Virtual Keys."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ApplicationLifecycle(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class ApplicationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")
    allowed_models: List[str] = Field(default_factory=list)
    monthly_token_quota: int = Field(default=1_000_000, gt=0)


class ApplicationUpdate(BaseModel):
    description: Optional[str] = None
    allowed_models: Optional[List[str]] = None
    monthly_token_quota: Optional[int] = Field(default=None, gt=0)


class ApplicationLifecycleUpdate(BaseModel):
    target_state: ApplicationLifecycle
    reason: Optional[str] = None


class VirtualKey(BaseModel):
    id: str
    key_prefix: str
    key_hash: str
    application_id: str
    tenant_id: str
    created_at: int
    expires_at: Optional[int] = None
    is_revoked: bool = False


class VirtualKeyStatus(BaseModel):
    id: str
    key_prefix: str
    application_id: str
    tenant_id: str
    created_at: int
    is_revoked: bool
    provisioning_state: str


class Application(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    environment: str
    allowed_models: List[str]
    monthly_token_quota: int
    lifecycle_state: ApplicationLifecycle
    created_by: str
    created_at: int
    updated_at: int
    virtual_key_prefix: Optional[str] = None
