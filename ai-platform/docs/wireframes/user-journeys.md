# MVP User Journeys

**Phase:** 2 — Gate 2-approved design baseline  
**Scope:** Source workflows include identity, registry, routes, onboarding, approvals, MCP discovery/policy intent, advisory budgets, policy revisions, and read-only operations. Runtime integration is unverified. See [MVP scope](../architecture/mvp-scope.md).

All data shown in the local wireframe prototype is illustrative; it is not
connected to services. The separate console is a limited live API client, but
its gateway, database migration, and telemetry behavior is unverified.

## Journey A — Register an application and configure a route (A–F)

**Actors:** Developer; tenant administrator; platform operator for the test environment.  
**Goal:** Register an application, select an approved backend, and submit a route through Kubernetes resources. End-to-end inference is not implemented or verified.

1. The user signs in through the configured identity provider. The UI shows only tenant memberships resolved for that identity. If identity or membership lookup fails, the journey stops before tenant data loads.
2. The developer opens **Applications** and registers a uniquely named application in the authorized tenant. The API derives tenant ownership from authenticated context; the client does not choose it.
3. Development/staging registrations may return a one-time credential. Production applications remain drafts until a matching approval request is approved and consumed by activation.
4. A tenant administrator registers or selects an approved provider/model and supplies a Kubernetes Secret reference. The UI accepts the reference only; it never accepts or renders provider secret plaintext.
5. The administrator creates a route and optional supported OSS regex guardrail. Validation presents errors inline and a resource/diff preview. Invalid input does not create or apply a resource.
6. The administrator submits the validated desired configuration. The UI displays **Pending controller observation** after the Kubernetes API accepts the write; it does not display “Active” based on acknowledgement alone.
7. The UI changes to **Observed active** only after the relevant agentgateway controller/resource status has been read back and matched to the requested revision. Rejection, timeout, stale status, or unavailable Kubernetes API is shown as an explicit pending/error state with a correlation ID.
8. A real gateway request is a future integration validation step, not part of this source slice.
9. The user opens **Traces & usage** and **Audit events**. Configured sources are queried, while actual gateway usage remains unavailable unless exported and configured; audit behavior remains unverified.

**Failure branches:** Unauthorized tenant; duplicate application; unapproved model; missing Secret reference; route validation error; Kubernetes write denied; controller rejection; status timeout; gateway/backend request denied or unavailable; trace/audit ingestion unavailable. Each failure preserves the desired/observed distinction and has a retry or next step only where safe.

## Journey B — Safely change a route

**Actors:** Tenant administrator; platform operator.  
**Goal:** Preview and validate a non-production route/policy change, then observe controller status.

1. Open **Routes & policies** and select a route in the test environment.
2. Edit the route/backend reference or supported regex policy. The form validates required fields and presents a proposed declarative resource diff.
3. Choose **Validate**. On success, show the validation result and generated-resource summary. On failure, retain edits and highlight actionable fields.
4. Choose **Apply to test environment**. Explain that this writes Gateway API/agentgateway resources through the Kubernetes API; it does not call an assumed gateway `/config/apply` endpoint.
5. Show **Pending controller observation** until the controller publishes status. Display **Observed active** only after verified read-back; display **Rejected**, **Apply failed**, or **Status unavailable** when appropriate.
6. Record the actor, tenant, resource identity, change summary, result and correlation ID in the audit view, without storing secret values.

**Boundaries:** Production application activation requires a separate matching approval. Route rollback restores a verified snapshot and submits desired state but does not guarantee recovery. Hard-budget behavior and claims based only on a gateway health probe are unsupported.

## Journey C — Register an MCP server and store policy intent

**Actors:** Tenant administrator; developer/test client.  
**Goal:** Discover real tools from an allowlisted MCP endpoint and record CEL policy intent. The policy is not enforced by agentgateway.

1. Register the HTTPS MCP endpoint. The service requires an exact host match in `MCP_ALLOWED_HOSTS`; operator network egress restrictions remain required.
2. Request discovery. The API calls `initialize` and `tools/list` with bounded timeout and redirects disabled. Show discovered tools or an explicit transport/protocol error.
3. Store CEL policy intent for a discovered tool. Show the state `not_published_to_gateway`; do not describe it as an authorization control.
4. No tool-call authorization or `tools/list` filtering is claimed. Authenticated MCP transport and pagination are not implemented.

**Failure branches:** Host allowlist denial, DNS/TLS/transport failure, malformed MCP result, unsupported policy expression, or discovery failure. Surface a safe error without disclosing credentials or request content.

## Journey D — Request onboarding and approve production activation

**Actors:** Tenant requester and a distinct tenant reviewer.
**Goal:** Submit and review application onboarding, then complete approved provisioning without exposing credentials beyond one-time delivery.

1. A tenant member submits an application name, environment, model list, and requested token quota.
2. A distinct reviewer approves or denies the request. Self-review is rejected server-side.
3. The requester completes an approved request. Eligible non-production provisioning can return a key once; production completion creates a draft without a key.
4. For production, the requester creates an `application_activation` approval referencing the application ID. A distinct approver decides it.
5. The requester/authorized operator activates the application with the exact approval ID. The API consumes the approval once and returns the key once after catalog provisioning.
6. If credential response delivery is lost, the key is not recoverable; operators must use the established revocation/replacement process. Retry and lost-response recovery require operational care.

## Journey E — Review budget and operational status

1. A tenant administrator configures an advisory monthly budget and alert threshold. A request for hard-cap enforcement is rejected.
2. Spend is shown only when the configured tenant-scoped Prometheus query returns an observed series; missing data displays **Unknown**, not zero.
3. An authorized user refreshes operations drift. The endpoint reads Kubernetes/controller observations and explicitly performs no writes or remediation.

## Journey F — Inspect and restore route revisions

1. A user loads persisted revisions for a tenant-owned route.
2. The UI displays revision state and checksum metadata; no secrets are included in the snapshot.
3. The user selects a source revision and submits rollback. The API verifies its checksum, restores desired route intent, and runs the existing apply path.
4. The UI reports the write/apply result separately from later controller observation. Rollback does not guarantee runtime recovery.

## Prototype-only walkthroughs

The static wireframe prototype may illustrate journeys with mock transitions, but every interaction must say **Illustrative only — no service call made**. The separate console calls the API; it must not fabricate credentials, discovery results, approval decisions, spend, audit evidence, or drift status.
