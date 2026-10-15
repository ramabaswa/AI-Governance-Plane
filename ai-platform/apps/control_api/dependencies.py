"""Control API dependencies for runtime integration clients."""

from integrations.agentgateway.client import AgentgatewayKubernetesClient


def get_agentgateway_kubernetes_client() -> AgentgatewayKubernetesClient:
    return AgentgatewayKubernetesClient()
