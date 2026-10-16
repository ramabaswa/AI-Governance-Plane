"""Focused unit tests for route validation at the integration boundary."""

import pytest
import yaml

from integrations.agentgateway.validator import AgentgatewayConfigValidator
from shared.contracts.model import ModelBackend, ProviderType
from shared.contracts.route import GatewayRoute
from shared.errors.exceptions import ValidationError


def _model(tenant_id="tenant-acme"):
    return ModelBackend(
        id="model-test",
        tenant_id=tenant_id,
        name="test-model",
        provider=ProviderType.ANTHROPIC,
        model_name="claude-test",
        secret_ref="provider-secret/api-key",
        cost_per_1k_input_tokens=0,
        cost_per_1k_output_tokens=0,
        is_active=True,
        created_at=0,
        updated_at=0,
    )


def _route(tenant_id="tenant-acme"):
    return GatewayRoute(
        id="route-test",
        tenant_id=tenant_id,
        name="test-route",
        path_prefix="/v1/test",
        backend_model_id="model-test",
        failover_model_ids=[],
        traffic_weights={"model-test": 100},
        dlp_rules=[],
        rate_limit_rpm=None,
        revision_id=1,
        lifecycle_state="draft",
        created_at=0,
        updated_at=0,
    )


def test_validator_returns_resources_only_for_approved_tenant_model():
    result = AgentgatewayConfigValidator.validate_route_configuration(
        _route(),
        {"model-test": _model()},
    )

    assert result.status == "validated"
    resources = list(yaml.safe_load_all(result.kubernetes_crds))
    assert {resource["kind"] for resource in resources} == {
        "AgentgatewayBackend",
        "HTTPRoute",
        "AgentgatewayPolicy",
    }


def test_validator_rejects_cross_tenant_model_reference():
    with pytest.raises(ValidationError, match="Primary model"):
        AgentgatewayConfigValidator.validate_route_configuration(
            _route(),
            {"model-test": _model("tenant-globex")},
        )
