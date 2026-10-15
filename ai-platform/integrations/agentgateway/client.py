"""Kubernetes API client for server-side apply and observed resource status."""

from typing import Any

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError as Urllib3Error

from shared.errors.exceptions import GatewayReconciliationError


_RESOURCE_PLURALS = {
    "HTTPRoute": ("gateway.networking.k8s.io", "v1", "httproutes"),
    "AgentgatewayBackend": ("agentgateway.dev", "v1alpha1", "agentgatewaybackends"),
    "AgentgatewayPolicy": ("agentgateway.dev", "v1alpha1", "agentgatewaypolicies"),
}


class AgentgatewayKubernetesClient:
    """Writes only through the Kubernetes API; controller owns runtime reconciliation."""

    def __init__(
        self,
        custom_objects_api: Any | None = None,
        core_api: Any | None = None,
        *,
        field_manager: str = "ai-governance-plane",
    ):
        self.custom_objects_api = custom_objects_api
        self.core_api = core_api
        self.field_manager = field_manager

    def _initialize_apis(self) -> None:
        if self.custom_objects_api is not None and self.core_api is not None:
            return
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException as error:
                raise GatewayReconciliationError(
                    "Kubernetes credentials are not configured for route reconciliation"
                ) from error
        if self.custom_objects_api is None:
            self.custom_objects_api = client.CustomObjectsApi()
        if self.core_api is None:
            self.core_api = client.CoreV1Api()

    def apply(self, resources: list[dict[str, Any]]) -> None:
        if resources:
            self._initialize_apis()
        applied = 0
        for resource in resources:
            kind = resource.get("kind")
            if kind == "ConfigMap":
                metadata = resource.get("metadata", {})
                name, namespace = metadata.get("name"), metadata.get("namespace")
                if not isinstance(name, str) or not isinstance(namespace, str):
                    raise GatewayReconciliationError(
                        "Generated ConfigMap is missing its name or namespace",
                        details=[{"resource_kind": kind, "applied_count": applied}],
                    )
                try:
                    self.core_api.patch_namespaced_config_map(
                        name=name,
                        namespace=namespace,
                        body=resource,
                        field_manager=self.field_manager,
                        force=False,
                        _content_type="application/apply-patch+yaml",
                    )
                except ApiException as error:
                    raise GatewayReconciliationError(
                        f"Kubernetes rejected the desired ConfigMap '{name}'",
                        details=[{
                            "resource_kind": kind,
                            "resource_name": name,
                            "http_status": error.status,
                            "reason": error.reason,
                            "applied_count": applied,
                        }],
                    ) from error
                except Urllib3Error as error:
                    raise GatewayReconciliationError(
                        f"Kubernetes API is unavailable while applying ConfigMap '{name}'",
                        details=[{"resource_kind": kind, "resource_name": name, "applied_count": applied}],
                    ) from error
                applied += 1
                continue
            if kind not in _RESOURCE_PLURALS:
                raise GatewayReconciliationError(
                    f"Unsupported Kubernetes resource kind '{kind}'",
                    details=[{"resource_kind": kind, "applied_count": applied}],
                )
            group, version, plural = _RESOURCE_PLURALS[kind]
            metadata = resource.get("metadata", {})
            name, namespace = metadata.get("name"), metadata.get("namespace")
            if not isinstance(name, str) or not isinstance(namespace, str):
                raise GatewayReconciliationError(
                    "Generated Kubernetes resource is missing its name or namespace",
                    details=[{"resource_kind": kind, "applied_count": applied}],
                )
            try:
                self.custom_objects_api.patch_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    name=name,
                    body=resource,
                    field_manager=self.field_manager,
                    force=False,
                    _content_type="application/apply-patch+yaml",
                )
            except ApiException as error:
                raise GatewayReconciliationError(
                    f"Kubernetes rejected the desired {kind} resource '{name}'",
                    details=[{
                        "resource_kind": kind,
                        "resource_name": name,
                        "http_status": error.status,
                        "reason": error.reason,
                        "applied_count": applied,
                    }],
                ) from error
            except Urllib3Error as error:
                raise GatewayReconciliationError(
                    f"Kubernetes API is unavailable while applying {kind} '{name}'",
                    details=[{
                        "resource_kind": kind,
                        "resource_name": name,
                        "applied_count": applied,
                    }],
                ) from error
            applied += 1

    def read(self, resource: dict[str, Any]) -> dict[str, Any] | None:
        kind = resource["kind"]
        if kind == "ConfigMap":
            return None
        self._initialize_apis()
        group, version, plural = _RESOURCE_PLURALS[kind]
        metadata = resource["metadata"]
        try:
            return self.custom_objects_api.get_namespaced_custom_object(
                group=group,
                version=version,
                namespace=metadata["namespace"],
                plural=plural,
                name=metadata["name"],
            )
        except ApiException as error:
            if error.status == 404:
                return None
            raise GatewayReconciliationError(
                f"Unable to read observed Kubernetes resource '{metadata['name']}'",
                details=[{
                    "resource_kind": kind,
                    "resource_name": metadata["name"],
                    "http_status": error.status,
                    "reason": error.reason,
                }],
            ) from error
        except Urllib3Error as error:
            raise GatewayReconciliationError(
                f"Kubernetes API is unavailable while reading '{metadata['name']}'",
                details=[{"resource_kind": kind, "resource_name": metadata["name"]}],
            ) from error
