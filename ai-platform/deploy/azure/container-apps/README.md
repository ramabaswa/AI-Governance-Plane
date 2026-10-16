# Azure Container Apps deployment

This deployment template creates the Governance Plane Control API and its background reconciliation worker as separate Azure Container Apps. It expects an existing Container Apps managed environment, PostgreSQL database, Key Vault, and built container images.

## Current integration status

This deploys the Plane application containers; it does **not** make the current Kubernetes-based AgentGateway integration work on Container Apps. Route reconciliation, application key publication, and status inspection still use Kubernetes Gateway API resources and Kubernetes Secrets. The standalone AgentGateway resource API is not wired into these application flows yet. Do not treat a successful ACA deployment as a working standalone AgentGateway control plane.

AgentGateway's standalone admin API is unauthenticated and must stay bound to loopback. Do not expose port 15000 to the worker or the internet. Before enabling standalone reconciliation, implement and secure the supported config-resource API path and translate Plane intent into standalone configuration resources. See the [system overview](../../../docs/architecture/system-overview.md) and [MVP scope](../../../docs/architecture/mvp-scope.md).

## Prerequisites

- An ACA managed environment with network access to PostgreSQL and Key Vault.
- A PostgreSQL database with the Plane Alembic migrations applied (`alembic upgrade head`).
- A Key Vault using Azure RBAC, with versioned secrets named by the supplied secret URIs:
  - PostgreSQL SQLAlchemy URL as `DATABASE_SECRET_URI`.
  - A production `JWT_SECRET` of at least 32 characters as `JWT_SECRET_URI`.
- OIDC verification settings in `OIDC_PROVIDERS_JSON`, for example `{"https://issuer.example/":{"audience":"governance-api","jwks_url":"https://issuer.example/.well-known/jwks.json","algorithms":["RS256"]}}`. This config has no client secret; user access tokens are verified by issuer, audience, and JWKS.
- API and worker images pushed to a registry accessible to the managed environment.
- The deployer must be allowed to create user-assigned identities and role assignments at the Key Vault scope. The template grants each app identity `Key Vault Secrets User` on that vault.
- The managed environment's network and ingress design must permit the intended APIM and private caller paths.

The template creates separate user-assigned managed identities for API and worker. The API ingress defaults to `internal`; APIM and direct private callers need network connectivity to the managed environment. Set `CONTROL_API_INGRESS=external` only when the environment and upstream access controls are deliberately designed for public ingress.

## Deploy

Build and push the same application code as two image tags (the worker uses a different command):

```bash
az acr build --registry <registry-name> --image ai-governance-plane/api:<tag> \
  --file ai-platform/deploy/local/Dockerfile.api ai-platform
az acr build --registry <registry-name> --image ai-governance-plane/worker:<tag> \
  --file ai-platform/deploy/local/Dockerfile.api ai-platform
```

Then deploy the app resources:

```bash
RESOURCE_GROUP=<resource-group> \
MANAGED_ENVIRONMENT_ID=<aca-environment-resource-id> \
KEY_VAULT_ID=<key-vault-resource-id> \
DATABASE_SECRET_URI=<versioned-database-secret-uri> \
JWT_SECRET_URI=<versioned-jwt-secret-uri> \
OIDC_PROVIDERS_JSON='{"https://issuer.example/":{"audience":"governance-api","jwks_url":"https://issuer.example/.well-known/jwks.json","algorithms":["RS256"]}}' \
CONTROL_API_IMAGE=<registry>/ai-governance-plane/api:<tag> \
WORKER_IMAGE=<registry>/ai-governance-plane/worker:<tag> \
ai-platform/deploy/azure/container-apps/deploy.sh
```

The script does not print secret values; it passes only Key Vault secret URIs to Bicep. The database must already be migrated before the API's `/readyz` probe succeeds. Apply schema migrations as a controlled release step before switching API traffic.

## Traffic paths

- **APIM first hop:** APIM reaches the Control API over the private ACA environment. Configure APIM authentication and authorization independently; the Plane API still applies its own identity and tenant checks.
- **Direct private first hop:** approved callers reach the same internal Control API through private network connectivity and receive the same application-level authentication and authorization checks.
- **Agent traffic:** this template does not deploy AgentGateway or configure either agent-traffic path. Deploy and secure the standalone gateway separately until the standalone configuration adapter is implemented.

The legacy Kubernetes manifests under `deploy/kubernetes` remain for compatibility and are not required for this ACA template.
