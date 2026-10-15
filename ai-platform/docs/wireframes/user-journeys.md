# MVP User Journeys

**Phase:** 2 — Gate 2-approved design baseline  
**Scope:** A–F design baseline. MCP (G), production approvals, and other deferred features are not part of the active API. See [MVP scope](../architecture/mvp-scope.md).

All data shown in the local wireframe prototype is illustrative; it is not
connected to services. The separate console is a limited live API client, but
its gateway, database migration, and telemetry behavior is unverified.

## Journey A — Register an application and configure a route (A–F)

**Actors:** Developer; tenant administrator; platform operator for the test environment.  
**Goal:** Register an application, select an approved backend, and submit a route through Kubernetes resources. End-to-end inference is not implemented or verified.

1. The user signs in through the configured identity provider. The UI shows only tenant memberships resolved for that identity. If identity or membership lookup fails, the journey stops before tenant data loads.
2. The developer opens **Applications** and registers a uniquely named application in the authorized tenant. The API derives tenant ownership from authenticated context; the client does not choose it.
3. Development/staging registrations may return a one-time credential. Production applications remain drafts without credentials because the approval workflow is deferred.
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

**Not part of this journey:** Production promotion, HITL approval, automatic rollback, hard-budget behavior, or a claim that a gateway health probe proves a particular config is active. A prior revision may be restored only after a separately approved rollback design.

## Journey C — Register and govern an MCP server (deferred)

**Actors:** Tenant administrator; developer/test client.  
**Goal:** Future-scope only; no MCP workflow is mounted in the active API.

1. Register the test MCP server using a validated endpoint and explicit tenant ownership. Display the endpoint as unverified until discovery succeeds.
2. Request discovery from the approved management integration. Show loading, discovered timestamp, server identity, tool names and a clear failure message if the server is unreachable or returns an error.
3. Select a tool authorization rule using the pinned OSS policy capability. Show the exact rule inputs and validation result; do not present an arbitrary CEL rule as supported until compatibility has been verified.
4. Apply the policy using the same Kubernetes resource/controller path. Show pending/observed/rejected status as in Journey B.
5. Send one allowed tool request and one denied tool request through the real agentgateway test deployment. Verify both that the allowed call reaches the test MCP server and that the denied call does not.
6. Confirm `tools/list` visibility behavior separately. Existing upstream test evidence distinguishes method names, but end-to-end filtering behavior is not established; the UI must not promise hidden tools until that compatibility gate passes.

**Failure branches:** SSRF/endpoint policy denial, DNS/TLS/transport failure, malformed MCP result, unsupported policy expression, controller rejection, allowed call rejected, denied call forwarded, or discovery and runtime tool catalogs differing. Surface the server, tool, method and correlation ID without disclosing credentials or request content.

## Prototype-only walkthroughs

The static browser prototype may illustrate these journeys with mock transitions, but every interaction must say **Illustrative only — no service call made**. It must not mint a plausible credential, claim a write succeeded, claim a runtime is active, or fabricate traces, audit signatures, budget enforcement, approval decisions, or drift results.
