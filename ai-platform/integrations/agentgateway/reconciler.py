"""Apply desired Kubernetes resources and read their controller-reported status."""

from typing import Any

from integrations.agentgateway.client import AgentgatewayKubernetesClient
from integrations.agentgateway.translator import AgentgatewayDeclarativeTranslator
from shared.contracts.model import ModelBackend
from shared.contracts.route import GatewayRoute


def _condition_records(resource: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    status = resource.get("status", {})
    direct = status.get("conditions")
    if isinstance(direct, list):
        return direct
    if kind == "HTTPRoute":
        parents = status.get("parents", [])
        return [
            condition
            for parent in parents
            for condition in parent.get("conditions", [])
        ]
    ancestors = status.get("ancestors", [])
    return [
        condition
        for ancestor in ancestors
        for condition in ancestor.get("conditions", [])
    ]


def _condition_matches_generation(condition: dict[str, Any], generation: Any) -> bool:
    return (
        isinstance(generation, int)
        and not isinstance(generation, bool)
        and condition.get("observedGeneration") == generation
    )


class AgentgatewayReconciler:
    """No direct gateway admin API is used; Kubernetes controllers own runtime state."""

    def __init__(self, kubernetes_client: AgentgatewayKubernetesClient | None = None):
        self.kubernetes_client = kubernetes_client or AgentgatewayKubernetesClient()

    def resources(self, routes: list[GatewayRoute], models_by_id: dict[str, ModelBackend]) -> list[dict[str, Any]]:
        import os

        namespace = os.getenv("AGENTGATEWAY_NAMESPACE", "agentgateway-system")
        gateway_name = os.getenv("AGENTGATEWAY_GATEWAY_NAME", "ai-gateway")
        return AgentgatewayDeclarativeTranslator.generate_kubernetes_resources(
            routes,
            models_by_id,
            namespace=namespace,
            gateway_name=gateway_name,
        )

    def apply(
        self,
        routes: list[GatewayRoute],
        models_by_id: dict[str, ModelBackend],
        *,
        additional_resources: list[dict[str, Any]] | None = None,
    ) -> None:
        resources = [*(additional_resources or []), *self.resources(routes, models_by_id)]
        self.kubernetes_client.apply(resources)

    def read_status(self, route: GatewayRoute, models_by_id: dict[str, ModelBackend]) -> dict[str, Any]:
        resources = self.resources([route], models_by_id)
        observations = []
        for desired in resources:
            observed = self.kubernetes_client.read(desired)
            if observed is None:
                observations.append({
                    "kind": desired["kind"],
                    "name": desired["metadata"]["name"],
                    "state": "missing",
                    "conditions": [],
                })
                continue

            conditions = _condition_records(observed, desired["kind"])
            observed_generation = observed.get("metadata", {}).get("generation")
            current_conditions = [
                condition
                for condition in conditions
                if _condition_matches_generation(condition, observed_generation)
            ]
            accepted = [
                condition for condition in current_conditions
                if condition.get("type") == "Accepted"
            ]
            resolved = [
                condition for condition in current_conditions
                if condition.get("type") == "ResolvedRefs"
            ]
            labels = desired["metadata"].get("labels", {})
            observed_labels = observed.get("metadata", {}).get("labels", {})
            revision_matches = (
                desired["kind"] not in {"HTTPRoute", "AgentgatewayPolicy"}
                or observed_labels.get("governance-plane.io/revision")
                == labels.get("governance-plane.io/revision")
            )
            rejected = any(
                condition.get("type") in {"Accepted", "ResolvedRefs"}
                and condition.get("status") == "False"
                for condition in current_conditions
            )
            ready = (
                revision_matches
                and bool(accepted)
                and all(condition.get("status") == "True" for condition in accepted)
            )
            if desired["kind"] == "HTTPRoute":
                ready = ready and bool(resolved) and all(
                    condition.get("status") == "True" for condition in resolved
                )
            observations.append({
                "kind": desired["kind"],
                "name": desired["metadata"]["name"],
                "state": "accepted" if ready else "rejected" if rejected else "pending",
                "conditions": [
                    {
                        "type": condition.get("type"),
                        "status": condition.get("status"),
                        "reason": condition.get("reason"),
                    }
                    for condition in conditions
                ],
            })

        active = bool(observations) and all(item["state"] == "accepted" for item in observations)
        rejected = any(item["state"] == "rejected" for item in observations)
        return {
            "state": "observed_active" if active else "rejected" if rejected else "pending",
            "observed_active": active,
            "resources": observations,
        }
