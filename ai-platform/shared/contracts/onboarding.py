"""Contracts for tenant-scoped application onboarding requests."""

from typing import List, Optional

from pydantic import BaseModel, Field


class OnboardingRequestCreate(BaseModel):
    application_name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")
    requested_models: List[str] = Field(default_factory=list)
    monthly_token_quota: int = Field(default=1_000_000, gt=0)


class OnboardingDecision(BaseModel):
    decision: str = Field(..., pattern=r"^(approved|denied)$")
    comments: Optional[str] = Field(default=None, max_length=2000)


class OnboardingRequest(BaseModel):
    id: str
    tenant_id: str
    requested_by: str
    application_name: str
    environment: str
    requested_models: List[str]
    monthly_token_quota: int
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[int] = None
    review_comments: Optional[str] = None
    application_id: Optional[str] = None
    created_at: int
