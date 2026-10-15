# User Guide

**Status:** Describes the limited A–F source implementation. Runtime behavior
and tests have not been verified for this handoff.

## Developers and AI engineers

- Sign in through the configured OIDC provider. The local token endpoint is
  available only in development.
- Use **Applications** to create an application in a tenant where you have
  membership. Development and staging registrations may return a credential
  once. Copy it at creation; it is not returned by later reads.
- Production registrations are saved as drafts and receive no credential.
  Production activation is blocked because an approval workflow is not
  included.
- Use **Models** to register provider/model metadata and a Kubernetes Secret
  reference. The Control API does not accept provider secret plaintext or
  proxy inference.
- Use **Routes** to validate and submit supported gateway resources. A
  successful Kubernetes write is not proof of controller acceptance or a
  working inference route; inspect the reported status.

No end-to-end request through a live agentgateway is demonstrated by this
source slice. Local Compose does not include agentgateway.

## Tenant administrators

- Manage permitted routes and supported regex guardrail configuration within
  your authorized tenant.
- Application lifecycle changes are permission-gated. Production activation
  cannot be completed without the deferred approval workflow.
- Tenant membership administration is restricted to platform administrators.

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

Self-service onboarding, MCP governance, approval queues, budget/cost
enforcement, and automated drift remediation are deferred. See [MVP
scope](../architecture/mvp-scope.md) and [developer setup](../developer-experience/setup.md).
