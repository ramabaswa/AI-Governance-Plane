"""Self-service application onboarding request endpoints."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from apps.control_api.dependencies import get_agentgateway_kubernetes_client
from features.database import get_db_session
from features.self_service_onboarding import service
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from shared.authorization.dependencies import (
    AuthenticatedUser,
    require_permission,
    require_tenant_context,
)
from shared.contracts.onboarding import (
    OnboardingDecision,
    OnboardingRequest,
    OnboardingRequestCreate,
)

router = APIRouter(prefix="/api/v1/onboarding", tags=["Self-Service Onboarding"])


@router.get("/requests", response_model=list[OnboardingRequest])
async def list_requests(
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("onboarding:create")),
    session: Session = Depends(get_db_session),
):
    return service.list_requests(
        session,
        tenant_id=tenant_id,
        actor=user.actor_id,
        reviewer=user.has_perm("onboarding:review"),
    )


@router.post("/requests", status_code=201, response_model=OnboardingRequest)
async def submit_request(
    request: OnboardingRequestCreate,
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("onboarding:create")),
    session: Session = Depends(get_db_session),
):
    return service.submit_request(
        session,
        tenant_id=tenant_id,
        actor=user.actor_id,
        request=request,
    )


@router.post("/requests/{request_id}/review", response_model=OnboardingRequest)
async def review_request(
    decision: OnboardingDecision,
    request_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("onboarding:review")),
    session: Session = Depends(get_db_session),
):
    return service.review_request(
        session,
        tenant_id=tenant_id,
        request_id=request_id,
        actor=user.actor_id,
        decision=decision,
    )


@router.post("/requests/{request_id}/complete")
async def complete_request(
    request_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("onboarding:create")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    request, raw_key = service.complete_request(
        session,
        tenant_id=tenant_id,
        request_id=request_id,
        actor=user.actor_id,
        kubernetes_client=kubernetes_client,
    )
    return {
        "success": True,
        "data": {
            "request": request,
            "virtual_key": raw_key,
            "credential_state": (
                "catalog_configured"
                if raw_key
                else "not_issued_approval_required"
                if request.environment == "production"
                else "already_issued_once_or_response_lost"
            ),
        },
    }
