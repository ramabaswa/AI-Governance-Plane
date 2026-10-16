"""Kubernetes apply/status behavior with deterministic API stubs."""

from kubernetes.client.exceptions import ApiException
from kubernetes import config

from integrations.agentgateway.client import AgentgatewayKubernetesClient
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from shared.contracts.model import ModelBackend, ProviderType
from shared.contracts.route import GatewayRoute


class FakeCustomObjectsApi:
    def __init__(self, *, accepted=True, fail_after=None):
        self.resources = {}
        self.accepted = accepted
        self.fail_after = fail_after
        self.observed_generation = 1

    def patch_namespaced_custom_object(self, **kwargs):
        if self.fail_after is not None and len(self.resources) == self.fail_after:
            raise ApiException(status=409, reason="field manager conflict")
        body = kwargs["body"]
        body.setdefault("metadata", {})["generation"] = 1
        key = (body["kind"], body["metadata"]["namespace"], body["metadata"]["name"])
        self.resources[key] = body
        return body

    def get_namespaced_custom_object(self, **kwargs):
        kind = {
            "httproutes": "HTTPRoute",
            "agentgatewaybackends": "AgentgatewayBackend",
            "agentgatewaypolicies": "AgentgatewayPolicy",
        }[kwargs["plural"]]
        key = (kind, kwargs["namespace"], kwargs["name"])
        resource = dict(self.resources[key])
        if not self.accepted:
            resource["status"] = {"conditions": [{
                "type": "Accepted",
                "status": "False",
                "reason": "Invalid",
                "observedGeneration": self.observed_generation,
            }]}
        elif kind == "HTTPRoute":
            resource["status"] = {"parents": [{
                "conditions": [
                    {
                        "type": "Accepted",
                        "status": "True",
                        "reason": "Accepted",
                        "observedGeneration": self.observed_generation,
                    },
                    {
                        "type": "ResolvedRefs",
                        "status": "True",
                        "reason": "ResolvedRefs",
                        "observedGeneration": self.observed_generation,
                    },
                ],
            }]}
        else:
            resource["status"] = {"conditions": [{
                "type": "Accepted",
                "status": "True",
                "reason": "Accepted",
                "observedGeneration": self.observed_generation,
            }]}
        return resource


class FakeCoreApi:
    def patch_namespaced_config_map(self, **kwargs):
        return kwargs["body"]


def _model():
    return ModelBackend(
        id="model-test",
        tenant_id="tenant-acme",
        name="claude",
        provider=ProviderType.ANTHROPIC,
        model_name="claude-3-5-sonnet",
        secret_ref="sec/key",
        cost_per_1k_input_tokens=0.003,
        cost_per_1k_output_tokens=0.015,
        is_active=True,
        created_at=0,
        updated_at=0,
    )


def _route():
    return GatewayRoute(
        id="route-test",
        tenant_id="tenant-acme",
        name="integration-route",
        path_prefix="/v1/integ",
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


def test_kubernetes_credentials_are_loaded_only_for_resource_operations(monkeypatch):
    def unexpected_load(*_args, **_kwargs):
        raise AssertionError("Kubernetes configuration should load on demand")

    monkeypatch.setattr(config, "load_incluster_config", unexpected_load)
    monkeypatch.setattr(config, "load_kube_config", unexpected_load)
    AgentgatewayKubernetesClient()


def test_reconciler_reports_only_controller_observed_status():
    api = FakeCustomObjectsApi(accepted=True)
    reconciler = AgentgatewayReconciler(AgentgatewayKubernetesClient(api, FakeCoreApi()))
    models = {"model-test": _model()}

    reconciler.apply([_route()], models)
    status = reconciler.read_status(_route(), models)
    assert status["state"] == "observed_active"
    assert status["observed_active"] is True
    assert len(api.resources) == 3


def test_reconciler_surfaces_controller_rejection():
    api = FakeCustomObjectsApi(accepted=False)
    reconciler = AgentgatewayReconciler(AgentgatewayKubernetesClient(api, FakeCoreApi()))
    models = {"model-test": _model()}

    reconciler.apply([_route()], models)
    status = reconciler.read_status(_route(), models)
    assert status["state"] == "rejected"
    assert status["observed_active"] is False


def test_reconciler_keeps_stale_route_revision_pending():
    api = FakeCustomObjectsApi(accepted=True)
    reconciler = AgentgatewayReconciler(AgentgatewayKubernetesClient(api, FakeCoreApi()))
    models = {"model-test": _model()}

    reconciler.apply([_route()], models)
    for resource in api.resources.values():
        if resource["kind"] in {"HTTPRoute", "AgentgatewayPolicy"}:
            resource["metadata"]["labels"]["governance-plane.io/revision"] = "0"

    status = reconciler.read_status(_route(), models)
    assert status["state"] == "pending"
    assert status["observed_active"] is False
    assert all(
        item["state"] == "pending"
        for item in status["resources"]
        if item["kind"] in {"HTTPRoute", "AgentgatewayPolicy"}
    )


def test_reconciler_does_not_accept_conditions_from_an_older_generation():
    api = FakeCustomObjectsApi(accepted=True)
    reconciler = AgentgatewayReconciler(AgentgatewayKubernetesClient(api, FakeCoreApi()))
    models = {"model-test": _model()}

    reconciler.apply([_route()], models)
    api.observed_generation = 0

    status = reconciler.read_status(_route(), models)
    assert status["state"] == "pending"
    assert status["observed_active"] is False


def test_reconciler_surfaces_partial_apply_conflicts():
    api = FakeCustomObjectsApi(fail_after=1)
    reconciler = AgentgatewayReconciler(AgentgatewayKubernetesClient(api, FakeCoreApi()))

    from shared.errors.exceptions import GatewayReconciliationError
    import pytest

    with pytest.raises(GatewayReconciliationError) as error:
        reconciler.apply([_route()], {"model-test": _model()})
    assert error.value.details[0]["applied_count"] == 1
