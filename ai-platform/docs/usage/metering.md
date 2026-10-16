# Observability, Usage, and Metering

**Status:** The implementation includes control-API request instrumentation,
configurable Tempo/Prometheus readers, and advisory budget records with optional
observed estimated-spend queries. Gateway usage, token accounting, and cost
calculation have not been verified as an end-to-end capability.

## Available source behavior

- The Control API can emit OpenTelemetry traces and API request counters when
  OTLP endpoints are configured.
- Tempo trace queries return observed trace fields; absent token or cost
  attributes are not fabricated.
- Prometheus metric queries are configuration-driven. Gateway metrics are
  unavailable unless the gateway exports suitable tenant-scoped series and
  matching query templates are configured.
- Control API request counters measure management API calls, not inference
  requests.

## Not implemented

- No verified `x-agentgateway-key-id` to tenant/application attribution pipeline
  exists in this slice.
- No inference-token totals, provider spend calculation, hard/soft budget
  enforcement, quota alerts, or 429 budget behavior are claimed. Monthly
  budgets and thresholds are advisory configuration only.
- Catalog price fields, if populated, are not evidence of actual provider
  usage or incurred cost.

Show missing sources and fields as unavailable, not zero. Do not use the
illustrative rates or metric examples in this document as billing data.
Configure `TEMPO_QUERY_URL`, `PROMETHEUS_QUERY_URL`, and any required
`PROMETHEUS_*_QUERY` templates only after validating the source metric names
and tenant labels for the deployed environment.
