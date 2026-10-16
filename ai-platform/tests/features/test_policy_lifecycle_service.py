"""Focused unit tests for policy revision integrity and tenant scoping."""

import pytest

from features.persistence import GatewayRouteRecord
from features.policy_lifecycle import service
from shared.errors.exceptions import ResourceNotFoundError, ValidationError


def test_route_revision_checksum_is_checked_before_restore(feature_session):
    route = feature_session.get(GatewayRouteRecord, "route-test")
    revision = service.create_route_revision(
        feature_session,
        row=route,
        actor="admin",
    )
    feature_session.flush()
    revision.snapshot["path_prefix"] = "/tampered"
    route.path_prefix = "/v1/changed"

    with pytest.raises(ValidationError, match="checksum"):
        service.prepare_route_rollback(
            feature_session,
            tenant_id="tenant-acme",
            route_id=route.id,
            revision_number=revision.revision,
            actor="admin",
        )
    assert route.path_prefix == "/v1/changed"


def test_revision_lookup_does_not_cross_tenant(feature_session):
    with pytest.raises(ResourceNotFoundError):
        service.list_route_revisions(
            feature_session,
            tenant_id="tenant-globex",
            route_id="route-test",
        )
