# AI Governance Plane

Tenant-scoped control plane and console for governing applications, models,
gateway routes, audit evidence, and observability. The target deployment is
Azure Container Apps, with standalone agentgateway as the runtime data plane.

The implementation and setup guide are in
[`ai-platform/README.md`](ai-platform/README.md). The current implementation
slice and explicit verification limitations are documented there.

## User manual

The Governance Plane is a management and evidence plane, not an inference
proxy. Use it to register applications and models, submit gateway
configuration, track approvals, and inspect governance evidence. Application
inference traffic flows through agentgateway, not through this Control API.
The current gateway writer is still Kubernetes-specific, so the ACA-only
target is not fully implemented.

### What is a tenant?

A **tenant** is the logical organization or workspace boundary used to separate
governance data and permissions. Tenant-owned applications, models, routes,
approvals, budgets, MCP registrations, and audit records are accessed in the
context of an authenticated user's active membership. A user's membership
determines their tenant roles and permissions; a platform administrator can
have platform-wide administrative access. A tenant is an authorization and
data-scoping concept in this product, not necessarily a separate database,
ACA environment, or billing account.

If you work with more than one tenant, choose an active membership when
prompted or as directed by your administrator. Do not use a tenant identifier
to which you have not been granted access. Resources and records are intended
to be isolated by the API according to that resolved tenant context.

### What features are available?

The **Background integration** column identifies what the feature contacts or
updates. The ACA target needs a protected, supported standalone config-resource
API path; the unauthenticated agentgateway admin API must remain on loopback.
The current source still uses Kubernetes resources for gateway writes, so
those operations are not ready for an ACA-only runtime. The Governance Plane
does not make inference requests on your behalf.

| Feature | What it is for | Background integration |
| --- | --- | --- |
| Applications and agents | Register tenant-owned applications, manage lifecycle, and inspect or revoke application credentials. Credentials are disclosed only at eligible creation/activation. | **Current code: Kubernetes ConfigMap. ACA target: standalone AgentGateway resource API (not implemented yet).** |
| Model catalog | Register provider/model metadata and a secret reference without sending provider secret plaintext to the API. | **Governance Plane database:** metadata is stored internally; ACA runtime secret resolution and model publication need implementation. |
| Gateway routes and guardrails | Validate and submit route/backend configuration and supported policy intent. A successful write is not proof of live traffic. | **Current code: Kubernetes resources. ACA target: standalone AgentGateway management API (not implemented yet).** |
| Approvals | Request and record reviewer decisions with separation of duties; production application activation uses a matching approval. | **Governance Plane database:** decisions are stored internally. A matching approval is consumed by production activation; approval itself does not call the gateway. |
| Self-service onboarding | Let an eligible tenant member request an application, have a distinct reviewer decide, then complete approved onboarding. | **Governance Plane database; current runtime provisioning uses Kubernetes.** ACA standalone credential publication is not implemented. |
| MCP governance | Register allowlisted HTTPS MCP servers, discover tools, and record policy intent. Tool policies are not enforced by agentgateway. | **MCP server directly for discovery:** initialization and tool listing call the allowlisted server. Registry/policy intent is stored internally, not sent to agentgateway. |
| FinOps and budgets | Configure advisory budget thresholds and view estimated spend only when tenant-scoped Prometheus data is configured. Hard caps are not enforced. | **Governance Plane database and optionally Prometheus:** budget settings are stored internally; configured Prometheus data may be queried for estimates. |
| Policy lifecycle | Review route policy revisions and submit a rollback to a prior revision; verify resulting runtime state separately. | **Governance Plane database and current Kubernetes integration.** Standalone ACA publish/readback is not implemented. |
| Operations | Inspect route/resource status and drift observations. This is read-only and does not automatically remediate drift. | **Current implementation reads Kubernetes status.** ACA runtime observation is not implemented. |
| Audit and observability | Inspect tenant-scoped audit events and query configured traces and metrics. Audit-chain storage is not immutable compliance evidence. | **Governance Plane database, and optionally Tempo/Prometheus:** audit events are stored internally; configured observability services supply traces/metrics. |
| Identity and access | Authenticate users and resolve tenant roles and permissions from active memberships. Tenant membership administration is restricted to platform administrators. | **OIDC identity provider for user authentication; Governance Plane database for tenant memberships/roles.** The API validates identity with the configured provider, then resolves authorization locally. It does not currently delegate tenant-role management to an external identity-management API. |

Feature availability depends on the user's role and on configured external
services. The [MVP scope](ai-platform/docs/architecture/mvp-scope.md) lists
additional implementation boundaries. Identity checks apply across the
authenticated features above; the table calls out each feature's additional
backend interactions.

### Getting started

1. Ask your platform operator for the deployed Control API URL, your identity
   provider account, tenant membership, and the permissions needed for your
   work. Tenant context is derived from your authenticated identity and
   membership; if you belong to multiple tenants, use only a tenant where you
   have active membership.
2. Open the console at `<control-api-url>/console/`. For interactive API
   reference and request exploration, open `<control-api-url>/docs`. The
   readiness endpoint is `<control-api-url>/readyz`.
3. Authenticate with your configured OIDC identity provider, then paste the
   issued access token into the console. The console holds the token in memory
   only. For direct API calls, send it as a bearer token in the
   `Authorization` header. The development token endpoint is only for a
   locally configured development environment; never use it as production
   authentication.
4. Select the workflow for your role below. If a feature is unavailable,
   request access from your tenant administrator or platform operator rather
   than sharing credentials or bypassing authorization.

The console is a limited API client and some workflows may require the API.
The [detailed user guide](ai-platform/docs/users/user-guide.md) and
[onboarding guide](ai-platform/docs/onboarding/onboarding-guide.md) describe
the current behavior and limitations.

### Workflows by stakeholder

**Application developers and AI engineers**

- Register an application in your tenant and select only models approved for
  that tenant. Non-production registrations may return a credential once;
  copy it immediately and store it in your approved secret manager.
- Production applications start as drafts. Request an
  `application_activation` approval, have a different authorized reviewer
  approve it, then activate with that approval. The resulting credential is
  also returned only once.
- Register provider/model metadata with a secret reference. Do not
  submit provider secret plaintext to the Control API.
- Validate a route before applying it. Check the returned apply result and
  then inspect runtime status; a control-plane write response does not prove
  that the gateway is serving traffic. Current status inspection still
  requires Kubernetes.

**Tenant administrators and platform operators**

- Manage tenant access, model registrations, routes, and supported guardrail
  configuration within your granted permissions. Tenant membership
  administration is reserved for platform administrators.
- Review onboarding and approval requests. Requesters cannot approve their
  own requests; production activation requires the separate approval flow
  described above.
- Set monthly budgets as advisory thresholds, inspect route policy revision
  history, and request a rollback when appropriate. A rollback submits desired
  state; verify the observed resource status afterward.
- The target deployment is Azure Container Apps. Current local Compose and
  Kubernetes assets are development/legacy paths; neither provides the target
  standalone AgentGateway integration.

**Finance and FinOps stakeholders**

- Configure or review tenant monthly budget amounts and alert thresholds.
- Treat these as advisory: hard-cap enforcement is not implemented. Spend is
  available only when a tenant-scoped Prometheus estimated-cost query is
  configured and returns data; missing data means unknown, not zero.

**MCP administrators**

- Register HTTPS MCP servers only for exact hosts allowed by the platform
  operator, then request discovery to read server initialization and tool
  listings.
- Treat stored MCP tool policies as policy intent only. They are not
  published to or enforced by agentgateway and must not be relied upon to
  authorize tool calls.

**Operations and security teams**

- Use operations views for read-only route/resource drift observations.
  Findings do not trigger automatic remediation.
- Use audit events to inspect tenant-scoped activity and the database-backed
  hash-chain evidence. It is not immutable storage or a compliance
  certification.
- Traces and metrics depend on configured Tempo and Prometheus sources.
  Inference usage and cost are not fabricated when metrics are unavailable.

For implementation boundaries, review the [MVP scope](ai-platform/docs/architecture/mvp-scope.md)
and [known issues](ai-platform/docs/releases/known-issues.md). Treat gateway
configuration and status as unverified until your operator has validated
them against the deployed controller and a real request path.

### OpenAPI reference

The API has a generated OpenAPI 3 specification at
`<control-api-url>/openapi.json`, served by FastAPI from the registered API
routes and schemas. Use that URL to download the machine-readable contract or
import it into an OpenAPI-compatible client. The interactive Swagger UI is at
`<control-api-url>/docs`; ReDoc is at `<control-api-url>/redoc`.

A separate checked-in OpenAPI file is not maintained: the generated
specification is the source of truth and stays aligned with the running API.
The schema describes the API contract; it does not imply that external
dependencies such as PostgreSQL, telemetry, or agentgateway are configured
or available.
