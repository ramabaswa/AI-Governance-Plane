from features.operations import service
from tests.feature_test_support import feature_database


class PendingReconciler:
    def __init__(self):
        self.read_count = 0

    def read_status(self, _route, _models):
        self.read_count += 1
        return {
            "state": "pending",
            "observed_active": False,
            "resources": [],
        }


def test_operations_reports_status_without_requesting_any_write():
    with feature_database() as session:
        reconciler = PendingReconciler()
        report = service.route_observations(
            session,
            tenant_id="tenant-acme",
            reconciler=reconciler,
        )
        assert report["write_performed"] is False
        assert report["drift_count"] == 1
        assert reconciler.read_count == 1
