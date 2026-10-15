"""Tenant-scoped Tempo traces and Prometheus metrics."""

from fastapi import APIRouter, Depends, Query

from features.observability.service import list_traces, query_metrics
from shared.authorization.dependencies import (
    AuthenticatedUser,
    get_current_user,
    require_tenant_context,
)
from shared.contracts.telemetry import ObservedTrace

router = APIRouter(prefix="/api/v1", tags=["Observability & Metrics"])


@router.get("/observability/traces", response_model=list[ObservedTrace])
async def get_traces(
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Return Tempo trace summaries scoped by the verified tenant resource attribute."""
    return list_traces(tenant_id, limit=limit)


@router.get("/dashboard/metrics")
async def get_dashboard_metrics(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Return configured tenant-scoped Prometheus query results only."""
    return {"success": True, "data": {"tenant_id": tenant_id, "metrics": query_metrics(tenant_id)}}
