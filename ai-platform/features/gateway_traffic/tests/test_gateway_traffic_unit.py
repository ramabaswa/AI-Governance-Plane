import pytest

from features.gateway_traffic import service
from tests.feature_test_support import feature_database
from shared.contracts.route import GatewayRouteCreate
from shared.errors.exceptions import ResourceNotFoundError, ValidationError


def test_route_creation_is_tenant_scoped_and_rejects_unsupported_rate_limit():
    with feature_database() as session:
        request = GatewayRouteCreate(
            name="new-route",
            path_prefix="/v1/new",
            backend_model_id="model-test",
        )
        route = service.create_route(
            session,
            tenant_id="tenant-acme",
            actor="admin",
            request=request,
        )
        assert route.lifecycle_state == "draft"
        assert route.traffic_weights == {"model-test": 100}

        with pytest.raises(ResourceNotFoundError):
            service.get_route(session, "tenant-globex", route.id)
        with pytest.raises(ValidationError):
            service.create_route(
                session,
                tenant_id="tenant-acme",
                actor="admin",
                request=GatewayRouteCreate(
                    name="limited-route",
                    path_prefix="/v1/limited",
                    backend_model_id="model-test",
                    rate_limit_rpm=10,
                ),
            )
