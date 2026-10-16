#!/usr/bin/env bash
set -euo pipefail

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI (az) is required." >&2
  exit 1
fi

: "${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
: "${MANAGED_ENVIRONMENT_ID:?Set MANAGED_ENVIRONMENT_ID to an existing ACA environment resource ID}"
: "${KEY_VAULT_ID:?Set KEY_VAULT_ID}"
: "${DATABASE_SECRET_URI:?Set DATABASE_SECRET_URI to a versioned Key Vault secret URI}"
: "${JWT_SECRET_URI:?Set JWT_SECRET_URI to a versioned Key Vault secret URI}"
: "${OIDC_PROVIDERS_JSON:?Set OIDC_PROVIDERS_JSON to JSON mapping issuer URLs to audience, jwks_url, and optional algorithms}"
: "${CONTROL_API_IMAGE:?Set CONTROL_API_IMAGE to the pushed API image}"
: "${WORKER_IMAGE:?Set WORKER_IMAGE to the pushed worker image}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCATION="${LOCATION:-$(az group show --name "$RESOURCE_GROUP" --query location -o tsv)}"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "${DEPLOYMENT_NAME:-ai-governance-plane}-$(( $(date +%s) ))" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters \
    managedEnvironmentId="$MANAGED_ENVIRONMENT_ID" \
    keyVaultId="$KEY_VAULT_ID" \
    databaseSecretUri="$DATABASE_SECRET_URI" \
    jwtSecretUri="$JWT_SECRET_URI" \
    oidcProvidersJson="$OIDC_PROVIDERS_JSON" \
    corsAllowedOrigins="${CORS_ALLOWED_ORIGINS:-}" \
    controlApiImage="$CONTROL_API_IMAGE" \
    workerImage="$WORKER_IMAGE" \
    location="$LOCATION" \
    controlApiIngress="${CONTROL_API_INGRESS:-internal}"
