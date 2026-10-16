"""Observe route reconciliation status without writing desired state."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from features.persistence import GatewayRouteRecord, ModelBackendRecord
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.contracts.model import ModelBackend
from shared.contracts.route import GatewayRoute


def route_observations(
    session: Session,
    *,
    tenant_id: str,
    reconciler: AgentgatewayReconciler,
) -> dict:
    route_rows = session.scalars(
        select(GatewayRouteRecord)
        .where(GatewayRouteRecord.tenant_id == tenant_id)
        .order_by(GatewayRouteRecord.name)
    ).all()
    model_rows = session.scalars(
        select(ModelBackendRecord).where(
            ModelBackendRecord.tenant_id == tenant_id,
            ModelBackendRecord.is_active.is_(True),
        )
    ).all()
    models = {
        model.id: ModelBackend.model_validate(model, from_attributes=True)
        for model in model_rows
    }
    observations = []
    for row in route_rows:
        route = GatewayRoute.model_validate(row, from_attributes=True)
        status = reconciler.read_status(route, models)
        observations.append({
            "route_id": row.id,
            "name": row.name,
            "desired_revision": row.revision_id,
            "persisted_state": row.lifecycle_state,
            "observed_state": status["state"],
            "observed_active": status["observed_active"],
            "resources": status["resources"],
            "drift": status["state"] != row.lifecycle_state,
        })
    return {
        "tenant_id": tenant_id,
        "source": "kubernetes-controller-status",
        "write_performed": False,
        "routes": observations,
        "drift_count": sum(item["drift"] for item in observations),
    }
