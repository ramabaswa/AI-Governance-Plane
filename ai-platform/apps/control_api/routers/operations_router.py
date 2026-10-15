"""Operational status, health probes, and drift detection router."""

from fastapi import APIRouter, Depends
from shared.authorization.dependencies import (
    get_current_user,
    require_permission,
    AuthenticatedUser,
)
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.contracts.audit import AuditAction
from features.state_store import STATE_STORE

router = APIRouter(prefix="/api/v1/operations", tags=["Operations & Drift"])


@router.get("/drift")
async def check_drift(
    current_user: AuthenticatedUser = Depends(require_permission("operations:read")),
):
    """Check drift between Control Plane desired state and agentgateway runtime."""
    reconciler = AgentgatewayReconciler()
    drift_status = await reconciler.check_drift()
    return {
        "success": True,
        "data": drift_status,
    }


@router.post("/reconcile")
async def force_reconciliation(
    current_user: AuthenticatedUser = Depends(require_permission("operations:reconcile")),
):
    """Force synchronization of all tenant desired state to agentgateway."""
    reconciler = AgentgatewayReconciler()
    res = await reconciler.reconcile_desired_state(
        routes=list(STATE_STORE.routes.values()),
        models_by_id=STATE_STORE.models,
        virtual_keys=[
            {"id": vk.id, "key_hash": vk.key_hash, "quota": 1_000_000}
            for vk in STATE_STORE.virtual_keys.values()
            if not vk.is_revoked
        ],
    )

    STATE_STORE.record_audit_event(
        tenant_id="platform",
        actor=current_user.subject,
        action=AuditAction.DRIFT_RECONCILED,
        resource_type="reconciliation",
        resource_id="agentgateway",
        details=res,
    )

    return {
        "success": True,
        "data": res,
    }
