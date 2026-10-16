# Known Limitations

**Release status:** Unreleased implementation snapshot  
**Verification:** The following limitations are based on source inspection.
Tests, migrations, containers, deployments, and live integrations have not been
run for this handoff.

## Integration and operations

- Local Compose does not start Kubernetes or agentgateway. Route/key apply
  requires a separately configured cluster, expected CRDs, namespace, RBAC,
  and referenced Secrets.
- The agentgateway v1.6.0 translation target and Kubernetes condition handling
  have not been verified against a live controller.
- No end-to-end inference request has been demonstrated. The Control API is
  not an inference proxy.
- Tempo and Prometheus readers depend on configured services and queries.
  Gateway request/token usage is not available unless the runtime exports
  tenant-scoped metrics and matching Prometheus queries are supplied.
- The production database migration and PostgreSQL durability/recovery have
  not been exercised.

## Product scope

- Production application activation requires an approved request; the new
  approval and onboarding workflows have not been exercised against a live
  deployment.
- MCP discovery requires a configured exact-host allowlist and egress controls.
  Stored tool policies are not published to or enforced by the gateway.
- Budget reporting depends on a month-scoped tenant Prometheus query. Hard-cap
  cost enforcement is unavailable.
- Operations reports read-only drift; automated remediation is not
  implemented. Route rollback depends on Kubernetes apply and controller
  status, neither of which has been live-validated.
- Provider health and Secret existence are not inferred from catalog entries.
- The audit hash chain is not an immutable/compliance ledger; retention,
  signing, and export guarantees are not established.

## Validation status

- Focused tests exist but have not been executed.
- The console has not been browser-validated for accessibility or end-to-end
  behavior.
- No security, dependency, or secret scan was run.
