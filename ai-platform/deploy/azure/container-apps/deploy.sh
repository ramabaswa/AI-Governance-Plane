#!/usr/bin/env bash
set -euo pipefail

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI (az) is required." >&2
  exit 1
fi

: "${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
: "${MANAGED_ENVIRONMENT_ID:?Set MANAGED_ENVIRONMENT_ID to an existing ACA environment resource ID}"
: "${KEY_VAULT_ID:?Set KEY_VAULT_ID}"
: "${DATABASE_SECRET_NAME:?Set DATABASE_SECRET_NAME to the Key Vault secret name for the PostgreSQL URL}"
: "${CONTAINER_REGISTRY_ID:?Set CONTAINER_REGISTRY_ID to the Azure Container Registry resource ID}"
: "${DATABASE_SECRET_URI:?Set DATABASE_SECRET_URI to a versioned Key Vault secret URI}"
: "${OIDC_PROVIDERS_JSON:?Set OIDC_PROVIDERS_JSON to JSON mapping issuer URLs to audience, jwks_url, and optional algorithms}"
: "${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:?Set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT; production startup requires it}"
: "${OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:?Set OTEL_EXPORTER_OTLP_METRICS_ENDPOINT; production startup requires it}"
: "${CONTROL_API_IMAGE:?Set CONTROL_API_IMAGE to the pushed API image}"
: "${WORKER_IMAGE:?Set WORKER_IMAGE to the pushed worker image}"

URI_SECRET_NAME="${DATABASE_SECRET_URI#*/secrets/}"
URI_SECRET_NAME="${URI_SECRET_NAME%%/*}"
if [[ "$URI_SECRET_NAME" != "$DATABASE_SECRET_NAME" ]]; then
  echo "DATABASE_SECRET_NAME must match the secret name in DATABASE_SECRET_URI." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_API_INGRESS="${CONTROL_API_INGRESS:-external}"
ACA_ENVIRONMENT_INTERNAL="$(az resource show --ids "$MANAGED_ENVIRONMENT_ID" --query properties.vnetConfiguration.internal -o tsv)"
if [[ "$CONTROL_API_INGRESS" == "external" && "$ACA_ENVIRONMENT_INTERNAL" != "true" ]]; then
  echo "External app ingress can be public in a public ACA environment. Use an internal ACA environment for private VNet ingress, or explicitly set CONTROL_API_INGRESS=internal for same-environment callers only." >&2
  exit 1
fi
LOCATION="${LOCATION:-$(az resource show --ids "$MANAGED_ENVIRONMENT_ID" --query location -o tsv)}"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "${DEPLOYMENT_NAME:-ai-governance-plane}-$(( $(date +%s) ))" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters \
    managedEnvironmentId="$MANAGED_ENVIRONMENT_ID" \
    keyVaultId="$KEY_VAULT_ID" \
    databaseSecretName="$DATABASE_SECRET_NAME" \
    containerRegistryId="$CONTAINER_REGISTRY_ID" \
    databaseSecretUri="$DATABASE_SECRET_URI" \
    oidcProvidersJson="$OIDC_PROVIDERS_JSON" \
    corsAllowedOrigins="${CORS_ALLOWED_ORIGINS:-}" \
    otelTracesEndpoint="$OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" \
    otelMetricsEndpoint="$OTEL_EXPORTER_OTLP_METRICS_ENDPOINT" \
    tempoQueryUrl="${TEMPO_QUERY_URL:-}" \
    prometheusQueryUrl="${PROMETHEUS_QUERY_URL:-}" \
    controlApiImage="$CONTROL_API_IMAGE" \
    workerImage="$WORKER_IMAGE" \
    location="$LOCATION" \
    controlApiIngress="$CONTROL_API_INGRESS"
