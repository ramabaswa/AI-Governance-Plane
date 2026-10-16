import pytest

from features.gateway_traffic import service
from features.llm_governance import service as model_service
from tests.feature_test_support import feature_database
from shared.contracts.model import ModelBackendCreate, ProviderType
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


def test_route_with_unsupported_gateway_provider_is_not_persisted():
    with feature_database() as session:
        unsupported_model = model_service.create_model(
            session,
            tenant_id="tenant-acme",
            actor="admin",
            request=ModelBackendCreate(
                name="unsupported-vllm",
                provider=ProviderType.VLLM,
                model_name="local-model",
                secret_ref="provider-secret/api-key",
            ),
        )

        with pytest.raises(ValidationError, match="not supported by agentgateway v1.6.0"):
            service.create_route(
                session,
                tenant_id="tenant-acme",
                actor="admin",
                request=GatewayRouteCreate(
                    name="unsupported-route",
                    path_prefix="/v1/unsupported",
                    backend_model_id=unsupported_model.id,
                ),
            )
        assert all(
            route.name != "unsupported-route"
            for route in service.list_routes(session, "tenant-acme")
        )
