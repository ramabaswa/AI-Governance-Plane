from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.worker.reconciliation_worker import reconcile_pending_routes
from features.persistence import AuditEventRecord, GatewayRouteRecord, PolicyRevisionRecord
from features.policy_lifecycle.service import create_route_revision
from shared.contracts.audit import AuditAction
from shared.errors.exceptions import GatewayReconciliationError
from tests.feature_test_support import feature_database


class SuccessfulReconciler:
    def apply(self, routes, _models_by_id, *, additional_resources=None):
        assert len(routes) == 1
        assert additional_resources

    def read_status(self, _route, _models_by_id):
        return {
            "state": "observed_active",
            "observed_active": True,
            "resources": [{"kind": "HTTPRoute", "name": "route-test", "state": "accepted"}],
        }


class FailedReconciler:
    def apply(self, _routes, _models_by_id, *, additional_resources=None):
        raise GatewayReconciliationError("Kubernetes API unavailable")


def _prepare_pending_route(session):
    row = session.scalar(select(GatewayRouteRecord).where(GatewayRouteRecord.id == "route-test"))
    row.lifecycle_state = "pending"
    row.updated_at = 0
    create_route_revision(session, row=row, actor="admin")
    session.commit()


def test_worker_recovers_persisted_pending_route_and_observes_status():
    with feature_database() as session:
        _prepare_pending_route(session)
        factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

        processed = reconcile_pending_routes(
            factory,
            SuccessfulReconciler(),
            retry_interval_seconds=1,
        )

        assert processed == 1
        session.expire_all()
        route = session.get(GatewayRouteRecord, "route-test")
        assert route.lifecycle_state == "observed_active"
        revision = session.scalar(select(PolicyRevisionRecord))
        assert revision.state == "observed_active"


def test_worker_marks_kubernetes_apply_failure_as_failed():
    with feature_database() as session:
        _prepare_pending_route(session)
        factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

        processed = reconcile_pending_routes(
            factory,
            FailedReconciler(),
            retry_interval_seconds=1,
        )

        assert processed == 1
        session.expire_all()
        route = session.get(GatewayRouteRecord, "route-test")
        assert route.lifecycle_state == "failed"
        revision = session.scalar(select(PolicyRevisionRecord))
        assert revision.state == "failed"
        failure_event = session.scalar(
            select(AuditEventRecord).where(
                AuditEventRecord.action == AuditAction.ROUTE_STATUS_CHANGED.value,
            )
        )
        assert failure_event is not None
