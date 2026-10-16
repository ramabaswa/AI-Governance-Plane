# Developer Setup

See the [project README](../../README.md) for prerequisites, Python setup,
production configuration, migrations, and the unverified implementation
status.

## Local development

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ai-platform/
cd ai-platform
export ENVIRONMENT=development
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn apps.control_api.main:app --host 127.0.0.1 --port 8000 --reload
```

The API requires `DATABASE_URL` in every environment; use PostgreSQL for local
development and production. Development startup creates the schema and local
sample records; production does not.
Configure `JWT_SECRET` before local login; no built-in signing key is used.
The local login endpoint is available only when `ENVIRONMENT=development`.

The console is at `http://localhost:8000/console/`, API documentation is at
`http://localhost:8000/docs`, and health/readiness probes are at
`http://localhost:8000/healthz` and `http://localhost:8000/readyz`.

## Local services

Compose configuration is in `deploy/local/docker-compose.yml`. It starts the
database, runs `alembic upgrade head` as a one-shot migration service, and
starts the Control API and worker only after migrations succeed. It also starts
the console, OTel Collector, Tempo, and Prometheus, but not Kubernetes or
agentgateway. The Compose configuration requires local-only
`POSTGRES_PASSWORD`, `DATABASE_URL`, and `JWT_SECRET` values. Applying routes
or application key catalogs requires access to a Kubernetes cluster with the
configured resources and permissions.

Tests are documented in [test traceability](../features/test-traceability.md).
They have not been executed for this implementation handoff.
