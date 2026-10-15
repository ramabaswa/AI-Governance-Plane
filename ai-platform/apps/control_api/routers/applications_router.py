"""Tenant-scoped application and virtual-key endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from features.application_agent_registry import service
from apps.control_api.dependencies import get_agentgateway_kubernetes_client
from features.database import get_db_session
from integrations.agentgateway.client import AgentgatewayKubernetesClient
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_permission,
    require_tenant_context,
)
from shared.contracts.application import (
    Application,
    ApplicationCreate,
    ApplicationLifecycleUpdate,
    VirtualKeyStatus,
)

router = APIRouter(prefix="/api/v1/applications", tags=["Applications & Agents"])


@router.get("", response_model=List[Application])
async def list_applications(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """List persisted applications in the caller's authorized tenant."""
    return service.list_applications(session, tenant_id)


@router.post("", status_code=201)
async def register_application(
    req: ApplicationCreate,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("app:create")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    """Create an application and return an eligible generated credential once."""
    app, raw_key = service.create_application(
        session,
        tenant_id=tenant_id,
        created_by=current_user.subject,
        request=req,
        kubernetes_client=kubernetes_client,
    )
    return {
        "success": True,
        "data": {
            "application": app,
            "virtual_key": raw_key,
            "credential_state": (
                "catalog_configured"
                if raw_key is not None
                else "not_issued_approval_required"
            ),
            "gateway_observation": (
                "not_verified" if raw_key is not None else "not_applicable"
            ),
        },
    }


@router.get("/{app_id}", response_model=Application)
async def get_application(
    app_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("app:read")),
    session: Session = Depends(get_db_session),
):
    """Return 404 for applications outside the caller's tenant."""
    return service.get_application(session, tenant_id, app_id)


@router.post("/{app_id}/lifecycle")
async def update_application_lifecycle(
    req: ApplicationLifecycleUpdate,
    app_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("app:lifecycle")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    app = service.update_application_lifecycle(
        session,
        tenant_id=tenant_id,
        app_id=app_id,
        target_state=req.target_state,
        actor=current_user.subject,
        kubernetes_client=kubernetes_client,
    )
    return {"success": True, "data": app}


@router.post("/{app_id}/keys/revoke")
async def revoke_application_keys(
    app_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("app:update")),
    kubernetes_client: AgentgatewayKubernetesClient = Depends(get_agentgateway_kubernetes_client),
    session: Session = Depends(get_db_session),
):
    """Revoke every active credential issued for this application."""
    service.revoke_application_keys(
        session,
        tenant_id=tenant_id,
        app_id=app_id,
        actor=current_user.subject,
        kubernetes_client=kubernetes_client,
    )
    return {
        "success": True,
        "data": {
            "application_id": app_id,
            "desired_credential_state": "revoked",
            "gateway_observation": "not_verified",
        },
    }


@router.get("/{app_id}/keys", response_model=list[VirtualKeyStatus])
async def list_application_key_status(
    app_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("app:read")),
    session: Session = Depends(get_db_session),
):
    """Show key catalog state and prefixes only; verifier hashes and raw keys are never returned."""
    return service.application_key_status(session, tenant_id=tenant_id, app_id=app_id)
