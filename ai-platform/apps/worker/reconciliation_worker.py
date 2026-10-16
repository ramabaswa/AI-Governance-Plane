"""Recover interrupted, database-persisted route applies."""

import asyncio
import logging
import os
import signal
import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from features.application_agent_registry.service import (
    finalize_pending_revocations,
    tenant_api_key_configmap,
)
from features.audit_evidence.service import append_event
from features.database import SessionFactory
from features.persistence import GatewayRouteRecord, ModelBackendRecord
from features.policy_lifecycle import service as policy_lifecycle_service
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.contracts.audit import AuditAction
from shared.contracts.model import ModelBackend
from shared.contracts.route import GatewayRoute
from shared.errors.exceptions import GatewayReconciliationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reconciliation-worker")


def reconcile_pending_routes(
    session_factory: sessionmaker[Session] = SessionFactory,
    reconciler: AgentgatewayReconciler | None = None,
    *,
    retry_interval_seconds: int = 15,
) -> int:
    """Retry old pending route revisions from persistent desired state."""
    active_reconciler = reconciler or AgentgatewayReconciler()
    cutoff = int(time.time()) - retry_interval_seconds
    reconciled = 0

    with session_factory() as session:
        pending_rows = session.scalars(
            select(GatewayRouteRecord)
            .where(
                GatewayRouteRecord.lifecycle_state == "pending",
                GatewayRouteRecord.updated_at <= cutoff,
            )
            .order_by(GatewayRouteRecord.updated_at, GatewayRouteRecord.id)
        ).all()

        for row in pending_rows:
            tenant_id = row.tenant_id
            route_id = row.id
            actor = "reconciliation-worker"
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
            route = GatewayRoute.model_validate(row, from_attributes=True)
            try:
                active_reconciler.apply(
                    [route],
                    models,
                    additional_resources=[
                        tenant_api_key_configmap(session, tenant_id=tenant_id),
                    ],
                )
                finalize_pending_revocations(session, tenant_id)
                status = active_reconciler.read_status(route, models)
                row.lifecycle_state = status["state"]
                row.updated_at = int(time.time())
                policy_lifecycle_service.update_route_revision_state(
                    session,
                    tenant_id=tenant_id,
                    route_id=route_id,
                    revision_number=row.revision_id,
                    state=status["state"],
                    actor=actor,
                    details={
                        "observed_active": status["observed_active"],
                        "resources": status["resources"],
                    },
                )
                append_event(
                    session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action=(
                        AuditAction.ROUTE_OBSERVED_ACTIVE
                        if status["observed_active"]
                        else AuditAction.ROUTE_STATUS_CHANGED
                    ),
                    resource_type="gateway_route",
                    resource_id=route_id,
                    details={
                        "to": status["state"],
                        "revision_id": row.revision_id,
                        "source": "reconciliation_worker",
                    },
                )
                session.commit()
                reconciled += 1
            except GatewayReconciliationError as error:
                row.lifecycle_state = "failed"
                row.updated_at = int(time.time())
                policy_lifecycle_service.update_route_revision_state(
                    session,
                    tenant_id=tenant_id,
                    route_id=route_id,
                    revision_number=row.revision_id,
                    state="failed",
                    actor=actor,
                    details={"error": error.message, "details": error.details},
                )
                append_event(
                    session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action=AuditAction.ROUTE_STATUS_CHANGED,
                    resource_type="gateway_route",
                    resource_id=route_id,
                    details={
                        "to": "failed",
                        "revision_id": row.revision_id,
                        "source": "reconciliation_worker",
                    },
                )
                session.commit()
                logger.error(
                    "Route reconciliation failed for tenant=%s route=%s revision=%s: %s",
                    tenant_id,
                    route_id,
                    row.revision_id,
                    error.message,
                )
                reconciled += 1
    return reconciled


class ReconciliationWorker:
    def __init__(
        self,
        interval_seconds: int = 15,
        *,
        reconcile: Callable[[], int] = reconcile_pending_routes,
    ):
        if interval_seconds < 1:
            raise ValueError("Reconciliation interval must be at least one second")
        self.interval = interval_seconds
        self.reconcile = reconcile
        self.is_running = False

    async def run_loop(self) -> None:
        self.is_running = True
        logger.info("Database-backed reconciliation worker started (polling every %ds)", self.interval)
        while self.is_running:
            reconciled = await asyncio.to_thread(self.reconcile)
            if reconciled:
                logger.info("Reconciliation worker processed %d pending route revision(s)", reconciled)
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        logger.info("Stopping reconciliation worker...")
        self.is_running = False


async def main() -> None:
    worker = ReconciliationWorker(interval_seconds=int(os.getenv("RECONCILE_INTERVAL", "15")))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            pass
    await worker.run_loop()


if __name__ == "__main__":
    asyncio.run(main())
