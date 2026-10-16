"""Read-only tenant route operations and drift observations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.control_api.dependencies import get_agentgateway_kubernetes_client
from features.database import get_db_session
from features.operations import service
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.authorization.dependencies import (
    AuthenticatedUser,
    require_permission,
    require_tenant_context,
)

router = APIRouter(prefix="/api/v1/operations", tags=["Operations & Drift"])


@router.get("/drift")
async def check_route_drift(
    tenant_id: str = Depends(require_tenant_context),
    _user: AuthenticatedUser = Depends(require_permission("operations:read")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    return service.route_observations(
        session,
        tenant_id=tenant_id,
        reconciler=AgentgatewayReconciler(kubernetes_client),
    )
