"""Self-service onboarding request router."""

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from shared.authorization.dependencies import (
    get_current_user,
    require_tenant_context,
    AuthenticatedUser,
)
from features.state_store import STATE_STORE

router = APIRouter(prefix="/api/v1/onboarding", tags=["Self-Service Onboarding"])


class OnboardingRequest(BaseModel):
    application_name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")
    requested_models: List[str] = Field(default_factory=list)
    monthly_token_quota: int = Field(default=1_000_000, gt=0)
    dlp_enable_pci: bool = True
    dlp_enable_ssn: bool = True


@router.post("/request")
async def submit_onboarding_request(
    req: OnboardingRequest,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Process onboarding request and mint virtual key."""
    app, raw_key = STATE_STORE.register_application(
        tenant_id=tenant_id,
        name=req.application_name,
        description=f"Self-service provisioned agent ({req.environment})",
        environment=req.environment,
        allowed_models=req.requested_models,
        monthly_token_quota=req.monthly_token_quota,
        created_by=current_user.subject,
    )

    return {
        "success": True,
        "data": {
            "application_id": app.id,
            "application_name": app.name,
            "lifecycle_state": app.lifecycle_state.value,
            "virtual_key": raw_key,
            "agentgateway_sample_command": f"curl -X POST http://localhost:8080/v1/chat/completions -H 'Authorization: Bearer {raw_key}'",
        },
    }
