import pytest

from features.persistence import GatewayRouteRecord
from features.policy_lifecycle import service
from tests.feature_test_support import feature_database
from shared.errors.exceptions import ValidationError


def test_rollback_restores_only_checksum_verified_snapshot():
    with feature_database() as session:
        route = session.get(GatewayRouteRecord, "route-test")
        revision = service.create_route_revision(session, row=route, actor="admin")
        session.flush()
        route.path_prefix = "/v1/changed"
        restored = service.prepare_route_rollback(
            session,
            tenant_id="tenant-acme",
            route_id=route.id,
            revision_number=revision.revision,
            actor="admin",
        )
        assert restored.path_prefix == "/v1/test"
        assert restored.lifecycle_state == "draft"

        revision.snapshot["path_prefix"] = "/v1/tampered"
        with pytest.raises(ValidationError, match="checksum"):
            service.prepare_route_rollback(
                session,
                tenant_id="tenant-acme",
                route_id=route.id,
                revision_number=revision.revision,
                actor="admin",
            )
