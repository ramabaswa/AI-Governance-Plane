"""Tests for the pinned Kubernetes-only agentgateway resource translator."""

import yaml
import pytest

from integrations.agentgateway.translator import (
    AgentgatewayDeclarativeTranslator,
)
from shared.contracts.model import ModelBackend, ProviderType
from shared.contracts.route import DLPAction, GatewayRoute, PromptGuardRule
from shared.errors.exceptions import ValidationError
from integrations.agentgateway.crd_schema import validate_generated_resource


def _models():
    return {
        "model-1": ModelBackend(
            id="model-1",
            tenant_id="tenant-acme",
            name="claude-3-5",
            provider=ProviderType.ANTHROPIC,
            model_name="claude-3-5-sonnet",
            secret_ref="anthropic-secret/api-key",
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
            is_active=True,
            created_at=0,
            updated_at=0,
        )
    }


def _route():
    return GatewayRoute(
        id="r-1",
        tenant_id="tenant-acme",
        name="k8s-chat",
        path_prefix="/v1/k8s-chat",
        backend_model_id="model-1",
        failover_model_ids=[],
        traffic_weights={"model-1": 100},
        dlp_rules=[
            PromptGuardRule(
                name="credit-card-mask",
                regex_patterns=[r"\b4[0-9]{12}(?:[0-9]{3})?\b"],
                action=DLPAction.MASK,
            ),
        ],
        rate_limit_rpm=None,
        revision_id=1,
        lifecycle_state="draft",
        created_at=0,
        updated_at=0,
    )


def test_translator_generates_backend_route_and_guard_policy_crds():
    resources = AgentgatewayDeclarativeTranslator.generate_kubernetes_resources(
        [_route()],
        _models(),
    )
    by_kind = {resource["kind"]: resource for resource in resources}
    assert set(by_kind) == {"AgentgatewayBackend", "HTTPRoute", "AgentgatewayPolicy"}

    backend = by_kind["AgentgatewayBackend"]
    assert backend["apiVersion"] == "agentgateway.dev/v1alpha1"
    assert backend["spec"]["ai"]["provider"]["anthropic"]["model"] == "claude-3-5-sonnet"
    assert backend["spec"]["policies"]["auth"]["secretRef"] == {
        "name": "anthropic-secret",
        "key": "api-key",
    }
    assert set(backend["spec"]["ai"]) == {"provider"}
    assert set(backend["spec"]["policies"]) == {"auth"}

    route = by_kind["HTTPRoute"]
    assert route["apiVersion"] == "gateway.networking.k8s.io/v1"
    assert route["spec"]["rules"][0]["backendRefs"][0]["weight"] == 100
    assert "port" not in route["spec"]["rules"][0]["backendRefs"][0]
    assert route["metadata"]["labels"]["governance-plane.io/revision"] == "1"

    policy = by_kind["AgentgatewayPolicy"]
    assert policy["metadata"]["labels"]["governance-plane.io/revision"] == "1"
    assert policy["spec"]["targetRefs"][0]["name"] == route["metadata"]["name"]
    assert policy["spec"]["traffic"]["apiKeyAuthentication"]["mode"] == "Strict"
    expressions = policy["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]
    assert "apiKey.tenant_id == \"tenant-acme\"" in expressions
    assert any("claude-3-5" in expression for expression in expressions)
    assert policy["spec"]["backend"]["ai"]["promptGuard"]["request"][0]["regex"] == {
        "matches": [r"\b4[0-9]{12}(?:[0-9]{3})?\b"],
        "action": "Mask",
    }


def test_translator_maps_domain_block_action_to_agentgateway_reject():
    route = _route().model_copy(update={
        "dlp_rules": [
            PromptGuardRule(
                name="block-sensitive",
                regex_patterns=[r"secret"],
                action=DLPAction.BLOCK,
            ),
        ],
    })
    resources = AgentgatewayDeclarativeTranslator.generate_kubernetes_resources(
        [route],
        _models(),
    )
    policy = next(resource for resource in resources if resource["kind"] == "AgentgatewayPolicy")
    action = policy["spec"]["backend"]["ai"]["promptGuard"]["request"][0]["regex"]["action"]
    assert action == "Reject"


def test_translator_rejects_provider_not_supported_by_pinned_release():
    models = _models()
    models["model-1"] = models["model-1"].model_copy(update={"provider": ProviderType.VLLM})
    with pytest.raises(ValidationError, match="not supported by agentgateway v1.6.0"):
        AgentgatewayDeclarativeTranslator.generate_kubernetes_resources([_route()], models)


def test_crd_contract_validator_rejects_unknown_backend_fields():
    backend = AgentgatewayDeclarativeTranslator.generate_kubernetes_resources([_route()], _models())[0]
    backend["spec"]["ai"]["policies"] = {}
    with pytest.raises(ValidationError, match="does not match v1.6.0 schema"):
        validate_generated_resource(backend)


def test_yaml_output_contains_only_generated_kubernetes_resources():
    output = AgentgatewayDeclarativeTranslator.generate_kubernetes_crds([_route()], _models())
    resources = list(yaml.safe_load_all(output))
    assert [resource["kind"] for resource in resources] == [
        "AgentgatewayBackend",
        "HTTPRoute",
        "AgentgatewayPolicy",
    ]
    assert all(resource["metadata"]["namespace"] == "agentgateway-system" for resource in resources)
