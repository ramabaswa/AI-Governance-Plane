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
   returned state and resource conditions. `pending` means a resource is
   missing, required conditions are absent, or a route resource's revision
   label is stale; `rejected` means the controller reported `Accepted=False`
   or `ResolvedRefs=False`.
2. Confirm Kubernetes API connectivity, namespace-scoped permissions, and
   the presence/version of the Gateway API and agentgateway CRDs.
3. Inspect the exact managed Kubernetes resources and controller conditions
   using the cluster's approved operator procedures.
4. Preserve the distinction between a desired resource, Kubernetes write
   acknowledgement, controller status, and successful inference. A successful
   write alone does not establish an active gateway configuration.
5. Use `GET /api/v1/operations/drift` for a read-only tenant-scoped
   controller-status comparison. It does not repair drift. Do not call a
   gateway `/config/apply` or `/status` admin endpoint; that is not the
   configured integration path.

## Approval or onboarding request

1. Read the request in the caller's authorized tenant.
2. Verify the target resource and proposed change independently before
   approving; requesters cannot decide their own requests.
3. Production application activation must reference a matching approved
   `application_activation` request. Approval IDs are single-use.
4. If catalog provisioning fails, review the returned error and key status;
   do not treat a failed or cleanup-pending credential as active.

## MCP discovery

1. Confirm the hostname exactly matches an entry in `MCP_ALLOWED_HOSTS`.
2. Confirm outbound network policy independently blocks unapproved/private
   destinations and redirects; the allowlist is not a firewall.
3. Check the discovery response and stored timestamp. A stored tool policy is
   not applied to agentgateway and does not authorize a tool call.

## FinOps data

1. Verify `PROMETHEUS_QUERY_URL` and the
   `PROMETHEUS_ESTIMATED_COST_QUERY` are configured for a month-to-date,
   tenant-scoped metric.
2. Treat absent samples or sources as unknown, never as zero spend.
3. Budget thresholds are advisory. Attempts to enable hard caps are rejected;
   runtime hard-cap enforcement is not available.

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
