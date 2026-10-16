# AI Governance Plane

The AI Governance Plane is a tenant-scoped management API and console for
application/model registration, gateway route configuration, audit evidence,
and observability. Inference traffic is intended to flow through agentgateway;
the Control API is not an inference proxy.

## Implementation status

The repository contains PostgreSQL-compatible SQLAlchemy persistence, generic
OIDC verification, Kubernetes server-side apply for agentgateway resources,
and OTel/Tempo/Prometheus integrations. Durable approval and onboarding
workflows, MCP server/tool registry, advisory budgets, route policy revision
history, and read-only operations observations are also available in source.
Unit and integration tests, database migrations, Kubernetes resources, and
telemetry behavior have **not been run or verified against live services**.
Local Compose does not include an agentgateway runtime. Do not treat API write
acknowledgements as proof that a gateway accepted a configuration or served a
request.

Important limits: MCP tool policies are not published/enforced by the gateway;
FinOps hard caps are unsupported; cost remains unknown without an explicitly
tenant-scoped Prometheus query; operations drift checks do not remediate
automatically; and only production application activation consumes an
approval. See [MVP scope](docs/architecture/mvp-scope.md) and
[test traceability](docs/features/test-traceability.md).

## Requirements

- Python 3.12 or later
- PostgreSQL for durable use (SQLite is available for development/test)
- Kubernetes credentials and the required Gateway API / agentgateway CRDs to
  apply and read gateway resources
- An OIDC provider for non-development authentication

## Local development

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ai-platform/
```

The development identity endpoint and automatic sample-data/schema setup are
enabled only when `ENVIRONMENT=development`. Configure a local `JWT_SECRET`
before using development login. The database defaults to a local SQLite file
only in development/test; `DATABASE_URL` is required in other environments.

To use the bundled local services, create `ai-platform/.env` with local-only
values (do not use production credentials):

```dotenv
POSTGRES_PASSWORD=replace-with-a-local-password
DATABASE_URL=postgresql+psycopg://governance:replace-with-a-local-password@postgres:5432/ai_governance
JWT_SECRET=replace-with-a-random-local-development-secret
```

Then run Compose from the repository root:

```bash
docker compose --env-file ai-platform/.env -f ai-platform/deploy/local/docker-compose.yml up --build
```

Compose starts PostgreSQL, the Control API, console, OTel Collector, Tempo,
and Prometheus. It does not start Kubernetes or agentgateway. Route and key
provisioning therefore require a separately configured Kubernetes cluster
with the expected CRDs, namespace, service account permissions, and referenced
secrets.

For direct development, set `ENVIRONMENT=development`, provide `JWT_SECRET`,
and optionally set `DATABASE_URL`; then start the API from `ai-platform/`:

```bash
uvicorn apps.control_api.main:app --host 127.0.0.1 --port 8000 --reload
```

The console is served at `/console/`, API documentation at `/docs`, and health
and readiness probes at `/healthz` and `/readyz`.

## Production configuration

Production deployments must use a pre-migrated database and configured OIDC
verification. Set `DATABASE_URL`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, and
`OIDC_JWKS_URL`. Configure `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and
`OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` for telemetry export. Set
`TEMPO_QUERY_URL` and `PROMETHEUS_QUERY_URL` to enable the corresponding
observability reads. Gateway request/token metrics remain unavailable unless
the gateway exports tenant-scoped metrics and suitable Prometheus query
templates are supplied.

Apply the production schema using Alembic after configuring `DATABASE_URL`:

```bash
cd ai-platform
alembic upgrade head
```

The Kubernetes deployment manifest expects operators to create the
`control-api-config` ConfigMap and `control-api-secrets` Secret. The
namespace-scoped writer permissions are in
[`deploy/kubernetes/agentgateway-writer-rbac.yaml`](deploy/kubernetes/agentgateway-writer-rbac.yaml);
review them against the installed CRDs and deployment namespaces before use.

## Tests

Tests are provided under `tests/`. They have not been run for this implementation
handoff. When execution is authorized, run from `ai-platform/`:

```bash
pytest tests/
```

For local setup details and feature boundaries, see
[developer setup](docs/developer-experience/setup.md) and
[MVP scope](docs/architecture/mvp-scope.md).
