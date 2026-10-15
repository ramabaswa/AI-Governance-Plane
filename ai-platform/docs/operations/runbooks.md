# Operations Notes

**Status:** Source-based operational notes; these procedures have not been
validated in a running environment.

## Control API unavailable

1. Check the service's `/healthz` endpoint for process health.
2. Check `/readyz` for database readiness. A not-ready response identifies
   the database dependency.
3. Inspect Control API logs and confirm `ENVIRONMENT`, `DATABASE_URL`, and
   required production OIDC settings.
4. Do not use local login outside development. Do not report the API healthy
   based only on `/healthz` if `/readyz` is failing.

## Route apply pending or failed

1. Inspect the route through the tenant-authorized routes API and review the
   returned state and resource conditions.
2. Confirm Kubernetes API connectivity, namespace-scoped permissions, and
   the presence/version of the Gateway API and agentgateway CRDs.
3. Inspect the exact managed Kubernetes resources and controller conditions
   using the cluster's approved operator procedures.
4. Preserve the distinction between a desired resource, Kubernetes write
   acknowledgement, controller status, and successful inference. A successful
   write alone does not establish an active gateway configuration.
5. Do not call a gateway `/config/apply` or `/status` admin endpoint; that is
   not the configured integration path. No force-reconcile or drift API is
   mounted.

## Telemetry unavailable

1. Confirm the configured OTLP export endpoints and OTel Collector health.
2. Confirm `TEMPO_QUERY_URL` and `PROMETHEUS_QUERY_URL` point to reachable
   services.
3. Confirm Prometheus query templates match metrics actually exported by the
   deployed environment and contain appropriate tenant scoping.
4. Treat absent gateway token/request metrics as unavailable. Control API
   counters are management traffic, not inference usage.

## Gateway or provider incident

The platform does not proxy inference and no end-to-end gateway/provider
request path has been validated. Use the agentgateway and provider operators'
approved monitoring/runbooks. Do not claim automated failover, rate limiting,
or budget enforcement based on this control-plane source.
