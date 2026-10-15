# Current Implementation State

**Status:** Approved A–F source implementation is present; Gate 3 verification
has not been performed.  
**Execution:** No application, test, build, migration, container, deployment, or
live integration command was run for this handoff, per the user's instruction.

## Summary

The repository contains a Python/FastAPI control API, browser console,
SQLAlchemy persistence models and Alembic migration, OIDC verification,
Kubernetes resource translation/apply/status readers, audit evidence,
observability integrations, tests, deployment files, and documentation.
Source presence is not proof of runtime integration, security certification,
or production readiness.

The active implementation scope is A–F: tenant-scoped identity and
authorization, application/key management, model registry, routes and
supported regex guardrails, plus audit and observability. MCP governance,
self-service onboarding, approvals, budgets/cost metering, and automated drift
remediation are deferred and are not mounted in the active API.

## Implementation and verification boundaries

| Area | Source state | Not verified |
|---|---|---|
| Identity and tenant access | Generic OIDC token verification and persisted tenant memberships; local login is environment-gated. | Real identity-provider/JWKS behavior and production configuration. |
| Persistence | SQLAlchemy schema, SQLite development fallback, PostgreSQL support, Alembic initial migration. Automatic schema creation/seeding is restricted to development/test. | Migration execution, PostgreSQL durability, backup/recovery. |
| Application keys | Raw keys are returned once; SHA-256 verifier hashes are stored; ConfigMap provisioning and revocation states are explicit. | Kubernetes apply/read behavior, gateway acceptance, revocation propagation, failure cleanup. |
| Gateway resources | Translator emits Kubernetes Gateway API and agentgateway resources; Kubernetes server-side apply and status read-back replace the former direct admin apply flow. | Live CRD compatibility, controller conditions, runtime route enforcement, end-to-end inference. |
| Guardrails | Supported regex prompt-guard subset is translated; unsupported route capabilities are rejected. | Live policy enforcement and upstream-version compatibility. |
| Audit | Persistent audit events use a hash chain; audit reads are recorded. | Chain tests, durability, retention, access-control matrix, compliance requirements. |
| Observability | Control API OTel instrumentation, Tempo trace querying, Prometheus metric queries, explicit unavailable states for unconfigured values. | Collector/exporter startup, live trace queries, tenant-scoped gateway metrics, real usage/token fields. |
| Console | Limited live console for authentication and the implemented applications, models, routes, observability, and audit surfaces. | Browser behavior, accessibility, escaping, and end-to-end usability. |
| Deployment | Local Compose includes PostgreSQL, Control API, console, OTel Collector, Tempo, and Prometheus; Kubernetes manifests define the Control API and scoped writer RBAC. | Compose/build, production cluster setup, RBAC and installed-CRD compatibility. Compose does not run agentgateway. |

The production deployment expects operators to provide the referenced
`control-api-config` ConfigMap and `control-api-secrets` Secret and to run
`alembic upgrade head` before serving requests. A Kubernetes write
acknowledgement is not controller observation. Inference requests are not
proxied through the Control API.

## Tests and evidence

Focused API, identity, translator, reconciliation, security-boundary, and
observability tests are present. None were run for this handoff. Current test
coverage and gaps are listed in [test traceability](../features/test-traceability.md).

No claims are made that tests pass, the migration applies, the application
builds, a deployment starts, or gateway/telemetry integrations work. Do not
execute those checks until the user authorizes them.

## Next gate

Implementation and related documentation are prepared for the approved A–F
slice. Review the source and test coverage, then obtain authorization before
running Gate 3 validation or beginning broader hardening. See the
[recovery plan](recovery-plan.md) for the gated work that remains.
