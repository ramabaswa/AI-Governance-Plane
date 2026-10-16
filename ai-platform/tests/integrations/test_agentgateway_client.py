"""Focused unit tests for the Kubernetes server-side apply client."""

import pytest
from kubernetes.client.exceptions import ApiException

from integrations.agentgateway.client import AgentgatewayKubernetesClient
from shared.errors.exceptions import GatewayReconciliationError


class FakeCustomObjectsApi:
    def __init__(self, *, read_error=None):
        self.apply_call = None
        self.read_error = read_error

    def patch_namespaced_custom_object(self, **kwargs):
        self.apply_call = kwargs
        return kwargs["body"]

    def get_namespaced_custom_object(self, **kwargs):
        if self.read_error:
            raise self.read_error
        return {"metadata": {"name": kwargs["name"]}}


def _route_resource():
    return {
        "apiVersion": "gateway.networking.k8s.io/v1",
        "kind": "HTTPRoute",
        "metadata": {"name": "route-test", "namespace": "gateway-test"},
        "spec": {},
    }


def test_apply_uses_server_side_apply_without_force_ownership():
    api = FakeCustomObjectsApi()
    client = AgentgatewayKubernetesClient(api, object(), field_manager="test-manager")

    client.apply([_route_resource()])

    assert api.apply_call["field_manager"] == "test-manager"
    assert api.apply_call["force"] is False
    assert api.apply_call["_content_type"] == "application/apply-patch+yaml"
    assert api.apply_call["plural"] == "httproutes"


def test_read_returns_none_only_for_not_found():
    api = FakeCustomObjectsApi(read_error=ApiException(status=404, reason="Not Found"))
    client = AgentgatewayKubernetesClient(api, object())

    assert client.read(_route_resource()) is None


def test_read_surfaces_non_not_found_api_errors():
    api = FakeCustomObjectsApi(read_error=ApiException(status=403, reason="Forbidden"))
    client = AgentgatewayKubernetesClient(api, object())

    with pytest.raises(GatewayReconciliationError) as error:
        client.read(_route_resource())
    assert error.value.details[0]["http_status"] == 403
