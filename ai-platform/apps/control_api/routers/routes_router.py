"""Tenant-scoped gateway route validation, storage, and observed status endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from features.database import get_db_session
from features.gateway_traffic import service
from features.llm_governance.service import get_tenant_models
from apps.control_api.dependencies import get_agentgateway_kubernetes_client
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from integrations.agentgateway.validator import AgentgatewayConfigValidator
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_permission,
    require_tenant_context,
)
from shared.contracts.route import GatewayRoute, GatewayRouteCreate, RouteValidationResult

router = APIRouter(prefix="/api/v1/routes", tags=["Gateway Routes & Policies"])


@router.get("", response_model=List[GatewayRoute])
async def list_routes(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    return service.list_routes(session, tenant_id)


@router.post("/validate", response_model=RouteValidationResult)
async def validate_route(
    req: GatewayRouteCreate,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Validate route capabilities and emit candidate Kubernetes resources only."""
    models = get_tenant_models(session, tenant_id)
    temporary_route = GatewayRoute(
        id="validation-only",
        tenant_id=tenant_id,
        name=req.name,
        path_prefix=req.path_prefix,
        backend_model_id=req.backend_model_id,
        failover_model_ids=req.failover_model_ids,
        traffic_weights=req.traffic_weights or {req.backend_model_id: 100},
        dlp_rules=req.dlp_rules,
        rate_limit_rpm=req.rate_limit_rpm,
        revision_id=1,
        lifecycle_state="draft",
        created_at=0,
        updated_at=0,
    )
    return AgentgatewayConfigValidator.validate_route_configuration(temporary_route, models)


@router.post("", status_code=201, response_model=GatewayRoute)
async def create_route(
    req: GatewayRouteCreate,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("route:create")),
    session: Session = Depends(get_db_session),
):
    return service.create_route(
        session,
        tenant_id=tenant_id,
        actor=current_user.actor_id,
        request=req,
    )


@router.post("/{route_id}/apply")
async def apply_route(
    route_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("route:apply")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    """Submit desired resources; report observed state only from controller status."""
    status = service.apply_route(
        session,
        tenant_id=tenant_id,
        route_id=route_id,
        actor=current_user.actor_id,
        reconciler=AgentgatewayReconciler(kubernetes_client),
    )
    return {"success": True, "data": status}


@router.get("/{route_id}/status")
async def get_route_status(
    route_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    return service.get_route_status(
        session,
        tenant_id=tenant_id,
        route_id=route_id,
        reconciler=AgentgatewayReconciler(kubernetes_client),
    )
