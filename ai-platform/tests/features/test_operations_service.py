"""Focused unit tests for read-only operations observations."""

from features.operations import service


class FakeReconciler:
    def __init__(self):
        self.routes = []

    def read_status(self, route, _models):
        self.routes.append(route.id)
        return {
            "state": "pending",
            "observed_active": False,
            "resources": [{"kind": "HTTPRoute", "state": "pending"}],
        }


def test_drift_observations_are_tenant_scoped_and_never_write(feature_session):
    reconciler = FakeReconciler()

    report = service.route_observations(
        feature_session,
        tenant_id="tenant-acme",
        reconciler=reconciler,
    )

    assert report["tenant_id"] == "tenant-acme"
    assert report["write_performed"] is False
    assert [route["route_id"] for route in report["routes"]] == ["route-test"]
    assert reconciler.routes == ["route-test"]
