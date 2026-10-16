# User Guide

**Status:** Describes available API source. Runtime behavior and tests have
not been verified for this handoff.

## Developers and AI engineers

- Sign in through the configured OIDC provider. The local token endpoint is
  available only in development.
- Use **Applications** to create an application in a tenant where you have
  membership. Development and staging registrations may return a credential
  once. Copy it at creation; it is not returned by later reads.
- Production registrations are saved as drafts and receive no credential.
  Create an `application_activation` approval request, have a different
  authorized reviewer approve it, then submit its ID when activating the
  application. A credential is returned once after catalog provisioning.
- Use **Models** to register provider/model metadata and a Kubernetes Secret
  reference. The Control API does not accept provider secret plaintext or
  proxy inference.
- Use **Routes** to validate and submit supported gateway resources. A
  successful Kubernetes write is not proof of controller acceptance or a
  working inference route; inspect the reported status.

No end-to-end request through a live agentgateway is demonstrated by this
source slice. Local Compose does not include agentgateway.

## Tenant administrators and reviewers

- Manage permitted routes and supported regex guardrail configuration within
  your authorized tenant.
- Review self-service onboarding and policy approval requests; requesters
  cannot approve their own changes.
- Configure advisory monthly budget amounts. Spend is reported only from a
  configured tenant-scoped Prometheus estimated-cost query; hard-cap
  enforcement is unavailable.
- Inspect route revision history and explicitly roll back a revision through
  the Kubernetes apply path. A rollback submission is not proof of runtime
  success.
- Tenant membership administration is restricted to platform administrators.

## MCP and operations

- Register MCP server endpoints over HTTPS. Live discovery calls
  `initialize` and `tools/list` only for exact hosts in `MCP_ALLOWED_HOSTS`.
  Use network egress controls as a second boundary.
- MCP tool policies are stored and audited, but are **not** published to or
  enforced by agentgateway. Do not rely on them to authorize tool calls.
- The operations drift endpoint is a read-only observation of route/resource
  status. It does not reconcile or mutate resources.

## Auditors

- Inspect tenant-scoped audit events and the database-backed hash-chain
  evidence.
- The hash chain is not immutable storage or a compliance certification.
  Signing, export, retention, and independent verification guarantees are not
  established.
- Traces and metrics depend on configured Tempo and Prometheus sources.
  Inference tokens and cost are not fabricated; missing fields remain
  unavailable.

## Not available in this implementation

Hard-cap budget enforcement, MCP runtime policy enforcement, approval quorum
and escalation, and automated drift remediation are not implemented. See
[MVP scope](../architecture/mvp-scope.md) and [developer
setup](../developer-experience/setup.md).
