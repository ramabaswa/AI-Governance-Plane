"""Validation of tenant route intent before generating Kubernetes resources."""

from typing import Dict

from shared.contracts.model import ModelBackend
from shared.contracts.route import GatewayRoute, RouteValidationResult
from shared.errors.exceptions import ValidationError
from shared.validation.regex_validator import validate_dlp_regex
from shared.validation.route_validator import validate_path_prefix, validate_traffic_weights
from integrations.agentgateway.translator import AgentgatewayDeclarativeTranslator


class AgentgatewayConfigValidator:
    """Validates supported route capabilities and returns candidate CRD manifests."""

    @staticmethod
    def validate_route_configuration(
        route: GatewayRoute,
        models_by_id: Dict[str, ModelBackend],
    ) -> RouteValidationResult:
        validate_path_prefix(route.path_prefix)
        if route.failover_model_ids:
            raise ValidationError("Failover routing is not supported by this implementation slice")
        if route.rate_limit_rpm is not None:
            raise ValidationError("Route-level rate limiting is not supported by this implementation slice")

        primary = models_by_id.get(route.backend_model_id)
        if primary is None or primary.tenant_id != route.tenant_id or not primary.is_active:
            raise ValidationError("Primary model is not active and approved for this tenant")
        weights = route.traffic_weights or {route.backend_model_id: 100}
        validate_traffic_weights(weights)
        if route.backend_model_id not in weights:
            raise ValidationError("Traffic weights must include the primary backend model")
        for model_id in weights:
            model = models_by_id.get(model_id)
            if model is None or model.tenant_id != route.tenant_id or not model.is_active:
                raise ValidationError(f"Weighted model '{model_id}' is not active and approved for this tenant")

        for rule in route.dlp_rules:
            for pattern in rule.regex_patterns:
                validate_dlp_regex(pattern)

        resources = AgentgatewayDeclarativeTranslator.generate_kubernetes_crds(
            routes=[route],
            models_by_id=models_by_id,
        )
        return RouteValidationResult(
            is_valid=True,
            status="validated",
            kubernetes_crds=resources,
            warnings=[],
        )
