"""Route policy revision history and explicit rollback operations."""

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.control_api.dependencies import get_agentgateway_kubernetes_client
from features.database import get_db_session
from features.gateway_traffic import service as route_service
from features.policy_lifecycle import service
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.authorization.dependencies import (
    AuthenticatedUser,
    require_permission,
    require_tenant_context,
)
from shared.contracts.policy_lifecycle import PolicyRevision

router = APIRouter(prefix="/api/v1/policies", tags=["Policy Lifecycle"])


class RollbackRequest(BaseModel):
    source_revision: int = Field(..., ge=1)


@router.get("/routes/{route_id}/revisions", response_model=list[PolicyRevision])
async def list_route_revisions(
    route_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    _user: AuthenticatedUser = Depends(require_permission("route:read")),
    session: Session = Depends(get_db_session),
):
    return service.list_route_revisions(
        session,
        tenant_id=tenant_id,
        route_id=route_id,
    )


@router.post("/routes/{route_id}/rollback")
async def rollback_route(
    request: RollbackRequest,
    route_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("route:apply")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    service.prepare_route_rollback(
        session,
        tenant_id=tenant_id,
        route_id=route_id,
        revision_number=request.source_revision,
        actor=user.subject,
    )
    result = route_service.apply_route(
        session,
        tenant_id=tenant_id,
        route_id=route_id,
        actor=user.subject,
        reconciler=AgentgatewayReconciler(kubernetes_client),
    )
    return {"success": True, "data": result}
