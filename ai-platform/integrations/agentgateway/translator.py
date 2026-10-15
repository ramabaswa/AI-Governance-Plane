"""Translate approved route intent into agentgateway v1.6 Kubernetes resources."""

import hashlib
import json
import re
from typing import Any

import yaml

from shared.contracts.model import ModelBackend
from shared.contracts.route import GatewayRoute
from shared.errors.exceptions import ValidationError
from shared.validation.regex_validator import validate_dlp_regex
from shared.validation.route_validator import validate_path_prefix, validate_traffic_weights
from features.application_agent_registry.naming import tenant_fingerprint

API_VERSIONS = {
    "HTTPRoute": "gateway.networking.k8s.io/v1",
    "AgentgatewayBackend": "agentgateway.dev/v1alpha1",
    "AgentgatewayPolicy": "agentgateway.dev/v1alpha1",
}


def _resource_name(prefix: str, tenant_id: str, object_id: str) -> str:
    suffix = hashlib.sha256(f"{tenant_id}:{object_id}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{suffix}"


class AgentgatewayDeclarativeTranslator:
    """Build Kubernetes API resources; no standalone or direct-admin config path exists."""

    @staticmethod
    def backend_resource_name(tenant_id: str, model_id: str) -> str:
        return _resource_name("model", tenant_id, model_id)

    @staticmethod
    def route_resource_name(tenant_id: str, route_id: str) -> str:
        return _resource_name("route", tenant_id, route_id)

    @classmethod
    def generate_kubernetes_resources(
        cls,
        routes: list[GatewayRoute],
        models_by_id: dict[str, ModelBackend],
        namespace: str = "agentgateway-system",
        gateway_name: str = "ai-gateway",
    ) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        for route in routes:
            validate_path_prefix(route.path_prefix)
            if route.failover_model_ids:
                raise ValidationError("Failover routing is not supported by this implementation slice")
            if route.rate_limit_rpm is not None:
                raise ValidationError("Route-level rate limiting is not supported by this implementation slice")
            weights = route.traffic_weights or {route.backend_model_id: 100}
            validate_traffic_weights(weights)
            if route.backend_model_id not in weights:
                raise ValidationError("Traffic weights must include the primary backend model")
            for rule in route.dlp_rules:
                for pattern in rule.regex_patterns:
                    validate_dlp_regex(pattern)
        needed_model_ids = {
            model_id
            for route in routes
            for model_id in (route.traffic_weights or {route.backend_model_id: 100})
        }
        for model_id in sorted(needed_model_ids):
            model = models_by_id.get(model_id)
            if model is None or not model.is_active:
                raise ValidationError(f"Weighted model '{model_id}' is not active and approved")
            if model.base_url:
                raise ValidationError("Custom provider endpoint overrides are not supported")
            tenants = {route.tenant_id for route in routes if model_id in (route.traffic_weights or {route.backend_model_id: 100})}
            if tenants != {model.tenant_id}:
                raise ValidationError(f"Weighted model '{model_id}' is not approved for the route tenant")
            secret_parts = model.secret_ref.split("/")
            if (
                len(secret_parts) != 2
                or not all(secret_parts)
                or not re.fullmatch(r"[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?", secret_parts[0])
                or not re.fullmatch(r"[A-Za-z0-9._-]+", secret_parts[1])
            ):
                raise ValidationError(
                    "Model secret_ref must use the 'secret-name/key' format in the gateway namespace",
                    details=[{"field": "secret_ref", "model_id": model.id}],
                )
            secret_name, secret_key = secret_parts
            resources.append({
                "apiVersion": API_VERSIONS["AgentgatewayBackend"],
                "kind": "AgentgatewayBackend",
                "metadata": {
                    "name": cls.backend_resource_name(model.tenant_id, model.id),
                    "namespace": namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "ai-governance-plane",
                        "governance-plane.io/tenant": tenant_fingerprint(model.tenant_id),
                    },
                },
                "spec": {
                    "ai": {
                        "provider": {
                            model.provider.value: {
                                "model": model.model_name,
                            },
                        },
                    },
                    "policies": {
                        "auth": {
                            "secretRef": {
                                "name": secret_name,
                                "key": secret_key,
                            },
                        },
                    },
                },
            })

        for route in routes:
            model = models_by_id.get(route.backend_model_id)
            if model is None:
                raise ValidationError(f"Primary model '{route.backend_model_id}' is not approved")
            if model.tenant_id != route.tenant_id or not model.is_active:
                raise ValidationError(f"Primary model '{model.id}' is not active in this tenant")
            route_name = cls.route_resource_name(route.tenant_id, route.id)
            weights = route.traffic_weights or {route.backend_model_id: 100}
            backend_refs = []
            for model_id, weight in sorted(weights.items()):
                weighted_model = models_by_id.get(model_id)
                if weighted_model is None or weighted_model.tenant_id != route.tenant_id:
                    raise ValidationError(f"Weighted model '{model_id}' is not approved for this tenant")
                if not weighted_model.is_active:
                    raise ValidationError(f"Weighted model '{model_id}' is inactive")
                backend_refs.append({
                    "group": "agentgateway.dev",
                    "kind": "AgentgatewayBackend",
                    "name": cls.backend_resource_name(weighted_model.tenant_id, weighted_model.id),
                    "weight": weight,
                })

            resources.append({
                "apiVersion": API_VERSIONS["HTTPRoute"],
                "kind": "HTTPRoute",
                "metadata": {
                    "name": route_name,
                    "namespace": namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "ai-governance-plane",
                        "governance-plane.io/tenant": tenant_fingerprint(route.tenant_id),
                    },
                },
                "spec": {
                    "parentRefs": [{
                        "group": "gateway.networking.k8s.io",
                        "kind": "Gateway",
                        "name": gateway_name,
                    }],
                    "rules": [{
                        "matches": [{
                            "path": {
                                "type": "PathPrefix",
                                "value": route.path_prefix,
                            },
                        }],
                        "backendRefs": backend_refs,
                    }],
                },
            })

            request_rules = []
            for rule in route.dlp_rules:
                request_rules.extend(
                    {"regex": {"matches": [pattern], "action": rule.action.value}}
                    for pattern in rule.regex_patterns
                )
            allowed_model_expressions = [
                f"apiKey.allowed_models.exists(allowed_model, allowed_model == {json.dumps(models_by_id[model_id].name)})"
                for model_id in sorted(weights)
            ]
            resources.append({
                "apiVersion": API_VERSIONS["AgentgatewayPolicy"],
                "kind": "AgentgatewayPolicy",
                "metadata": {
                    "name": f"{route_name}-policy",
                    "namespace": namespace,
                    "labels": {
                        "app.kubernetes.io/managed-by": "ai-governance-plane",
                        "governance-plane.io/tenant": tenant_fingerprint(route.tenant_id),
                    },
                },
                "spec": {
                    "targetRefs": [{
                        "group": "gateway.networking.k8s.io",
                        "kind": "HTTPRoute",
                        "name": route_name,
                    }],
                    "traffic": {
                        "apiKeyAuthentication": {
                            "mode": "Strict",
                            "configMapSelector": {
                                "matchLabels": {
                                    "app.kubernetes.io/name": "ai-governance-api-keys",
                                    "governance-plane.io/tenant": tenant_fingerprint(route.tenant_id),
                                },
                            },
                        },
                        "authorization": {
                            "action": "Require",
                            "policy": {
                                "matchExpressions": [
                                    f"apiKey.tenant_id == {json.dumps(route.tenant_id)}",
                                    *allowed_model_expressions,
                                ],
                            },
                        },
                    },
                    **(
                        {
                            "backend": {
                                "ai": {
                                    "promptGuard": {
                                        "request": request_rules,
                                    },
                                },
                            },
                        }
                        if request_rules
                        else {}
                    ),
                },
            })

        return resources

    @classmethod
    def generate_kubernetes_crds(
        cls,
        routes: list[GatewayRoute],
        models_by_id: dict[str, ModelBackend],
        namespace: str = "agentgateway-system",
        gateway_name: str = "ai-gateway",
    ) -> str:
        resources = cls.generate_kubernetes_resources(routes, models_by_id, namespace, gateway_name)
        return yaml.safe_dump_all(resources, sort_keys=False)
