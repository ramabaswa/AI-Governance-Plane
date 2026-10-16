"""Deterministic validation for the Agentgateway v1.6.0 resource subset we emit."""

from typing import Any

from shared.errors.exceptions import ValidationError

AGENTGATEWAY_RELEASE = "v1.6.0"

_API_VERSIONS = {
    "HTTPRoute": "gateway.networking.k8s.io/v1",
    "AgentgatewayBackend": "agentgateway.dev/v1alpha1",
    "AgentgatewayPolicy": "agentgateway.dev/v1alpha1",
}
_PROVIDER_FIELDS = {"anthropic", "bedrock", "gemini", "openai"}
_PROMPT_GUARD_ACTIONS = {"Audit", "Mask", "Reject"}


def _object(
    value: Any,
    path: str,
    *,
    required: set[str],
    allowed: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"Generated agentgateway resource field '{path}' must be an object")
    missing = required - value.keys()
    unknown = value.keys() - allowed if allowed is not None else set()
    if missing or unknown:
        raise ValidationError(
            f"Generated agentgateway resource field '{path}' does not match {AGENTGATEWAY_RELEASE} schema",
            details=[{
                "field": path,
                "missing": sorted(missing),
                "unknown": sorted(unknown),
            }],
        )
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"Generated agentgateway resource field '{path}' must be an array")
    return value


def _string(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"Generated agentgateway resource field '{path}' must be a non-empty string")


def validate_generated_resource(resource: dict[str, Any]) -> None:
    """Validate the exact resource shapes emitted by the control plane."""
    resource = _object(
        resource,
        "resource",
        required={"apiVersion", "kind", "metadata", "spec"},
        allowed={"apiVersion", "kind", "metadata", "spec"},
    )
    kind = resource["kind"]
    if kind not in _API_VERSIONS or resource["apiVersion"] != _API_VERSIONS[kind]:
        raise ValidationError(
            f"Generated resource API version is unsupported by agentgateway {AGENTGATEWAY_RELEASE}"
        )

    metadata = _object(
        resource["metadata"],
        "metadata",
        required={"name", "namespace", "labels"},
        allowed={"name", "namespace", "labels"},
    )
    _string(metadata["name"], "metadata.name")
    _string(metadata["namespace"], "metadata.namespace")
    labels = _object(metadata["labels"], "metadata.labels", required=set())
    for key, value in labels.items():
        _string(key, "metadata.labels key")
        _string(value, f"metadata.labels.{key}")

    if kind == "AgentgatewayBackend":
        _validate_backend(resource["spec"])
    elif kind == "HTTPRoute":
        _validate_http_route(resource["spec"])
    else:
        _validate_policy(resource["spec"])


def _validate_backend(spec: Any) -> None:
    spec = _object(spec, "spec", required={"ai", "policies"}, allowed={"ai", "policies"})
    ai = _object(spec["ai"], "spec.ai", required={"provider"}, allowed={"provider"})
    providers = _object(ai["provider"], "spec.ai.provider", required=set())
    if len(providers) != 1 or not set(providers).issubset(_PROVIDER_FIELDS):
        raise ValidationError(
            f"Generated backend provider is unsupported by agentgateway {AGENTGATEWAY_RELEASE}"
        )
    provider_name, provider_settings = next(iter(providers.items()))
    provider_settings = _object(
        provider_settings,
        f"spec.ai.provider.{provider_name}",
        required={"model"},
        allowed={"model"},
    )
    _string(provider_settings["model"], f"spec.ai.provider.{provider_name}.model")

    policies = _object(spec["policies"], "spec.policies", required={"auth"}, allowed={"auth"})
    auth = _object(policies["auth"], "spec.policies.auth", required={"secretRef"}, allowed={"secretRef"})
    secret_ref = _object(
        auth["secretRef"],
        "spec.policies.auth.secretRef",
        required={"name", "key"},
        allowed={"name", "key"},
    )
    _string(secret_ref["name"], "spec.policies.auth.secretRef.name")
    _string(secret_ref["key"], "spec.policies.auth.secretRef.key")


def _validate_http_route(spec: Any) -> None:
    spec = _object(spec, "spec", required={"parentRefs", "rules"}, allowed={"parentRefs", "rules"})
    for index, parent in enumerate(_list(spec["parentRefs"], "spec.parentRefs")):
        parent = _object(parent, f"spec.parentRefs[{index}]", required={"name"}, allowed={"group", "kind", "name"})
        _string(parent["name"], f"spec.parentRefs[{index}].name")
    for rule_index, rule in enumerate(_list(spec["rules"], "spec.rules")):
        rule = _object(
            rule,
            f"spec.rules[{rule_index}]",
            required={"matches", "backendRefs"},
            allowed={"matches", "backendRefs"},
        )
        for match_index, match in enumerate(_list(rule["matches"], f"spec.rules[{rule_index}].matches")):
            match = _object(match, f"spec.rules[{rule_index}].matches[{match_index}]", required={"path"}, allowed={"path"})
            path = _object(
                match["path"],
                f"spec.rules[{rule_index}].matches[{match_index}].path",
                required={"type", "value"},
                allowed={"type", "value"},
            )
            if path["type"] != "PathPrefix":
                raise ValidationError("Generated HTTPRoute uses an unsupported path match type")
            _string(path["value"], "HTTPRoute path match value")
        for backend_index, backend in enumerate(_list(rule["backendRefs"], f"spec.rules[{rule_index}].backendRefs")):
            backend = _object(
                backend,
                f"spec.rules[{rule_index}].backendRefs[{backend_index}]",
                required={"group", "kind", "name", "weight"},
                allowed={"group", "kind", "name", "weight"},
            )
            for field in ("group", "kind", "name"):
                _string(backend[field], f"HTTPRoute backendRefs.{field}")
            if backend["kind"] != "AgentgatewayBackend" or not isinstance(backend["weight"], int):
                raise ValidationError("Generated HTTPRoute backend reference is invalid")


def _validate_policy(spec: Any) -> None:
    spec = _object(
        spec,
        "spec",
        required={"targetRefs", "traffic"},
        allowed={"targetRefs", "traffic", "backend"},
    )
    for index, target in enumerate(_list(spec["targetRefs"], "spec.targetRefs")):
        target = _object(
            target,
            f"spec.targetRefs[{index}]",
            required={"group", "kind", "name"},
            allowed={"group", "kind", "name"},
        )
        for field in ("group", "kind", "name"):
            _string(target[field], f"spec.targetRefs[{index}].{field}")
    traffic = _object(
        spec["traffic"],
        "spec.traffic",
        required={"apiKeyAuthentication", "authorization"},
        allowed={"apiKeyAuthentication", "authorization"},
    )
    api_key = _object(
        traffic["apiKeyAuthentication"],
        "spec.traffic.apiKeyAuthentication",
        required={"mode", "configMapSelector"},
        allowed={"mode", "configMapSelector"},
    )
    if api_key["mode"] != "Strict":
        raise ValidationError("Generated API-key authentication mode must be Strict")
    selector = _object(
        api_key["configMapSelector"],
        "spec.traffic.apiKeyAuthentication.configMapSelector",
        required={"matchLabels"},
        allowed={"matchLabels"},
    )
    _object(selector["matchLabels"], "spec.traffic.apiKeyAuthentication.configMapSelector.matchLabels", required=set())
    authorization = _object(
        traffic["authorization"],
        "spec.traffic.authorization",
        required={"action", "policy"},
        allowed={"action", "policy"},
    )
    if authorization["action"] != "Require":
        raise ValidationError("Generated authorization action must be Require")
    policy = _object(
        authorization["policy"],
        "spec.traffic.authorization.policy",
        required={"matchExpressions"},
        allowed={"matchExpressions"},
    )
    for expression in _list(policy["matchExpressions"], "spec.traffic.authorization.policy.matchExpressions"):
        _string(expression, "spec.traffic.authorization.policy.matchExpressions[]")

    if "backend" in spec:
        backend = _object(spec["backend"], "spec.backend", required={"ai"}, allowed={"ai"})
        ai = _object(backend["ai"], "spec.backend.ai", required={"promptGuard"}, allowed={"promptGuard"})
        prompt_guard = _object(
            ai["promptGuard"],
            "spec.backend.ai.promptGuard",
            required={"request"},
            allowed={"request"},
        )
        for index, rule in enumerate(_list(prompt_guard["request"], "spec.backend.ai.promptGuard.request")):
            rule = _object(
                rule,
                f"spec.backend.ai.promptGuard.request[{index}]",
                required={"regex"},
                allowed={"regex"},
            )
            regex = _object(
                rule["regex"],
                f"spec.backend.ai.promptGuard.request[{index}].regex",
                required={"matches", "action"},
                allowed={"matches", "action"},
            )
            if regex["action"] not in _PROMPT_GUARD_ACTIONS:
                raise ValidationError(
                    f"Prompt guard action is unsupported by agentgateway {AGENTGATEWAY_RELEASE}"
                )
            for pattern in _list(regex["matches"], "prompt guard regex matches"):
                _string(pattern, "prompt guard regex matches[]")
