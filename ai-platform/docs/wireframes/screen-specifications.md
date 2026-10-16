# Screen Specifications and Interaction States

**Phase:** 2 — Gate 2-approved design baseline  
**Architecture:** Use the Kubernetes Gateway API/agentgateway CRD write path in [system overview](../architecture/system-overview.md). Screen/API details below are design contracts; active source scope and verification are summarized in [MVP scope](../architecture/mvp-scope.md).

## Global interaction rules

- Authenticate first, derive tenant membership from trusted identity, and authorize each API request. A user-controlled tenant field/header is never sufficient authorization.
- Display the active tenant and actor context on every authenticated screen. If context cannot be resolved, render no tenant data.
- Label sample values, stale data and unsupported data sources. Never substitute a success-shaped mock for an error.
- Separate **desired**, **Kubernetes API accepted**, and **controller observed** state. A write acknowledgement does not mean runtime active.
- A missing telemetry/status source is **Unavailable** or **Unknown**, not zero, healthy, or in sync.
- Never display provider secrets, bearer tokens, complete API keys after one-time issuance, or sensitive inference content in the console.
- The clickable prototype is a static simulation. Every simulated transition must state that it made no service call.

## Screen catalog

### SCR-001 — Sign in and tenant context

- **Features:** F-001. **Roles:** Unauthenticated, then any authorized user.
- **Goal:** Authenticate through the configured OIDC identity provider and resolve available tenant memberships.
- **UI:** Sign-in action; identity-provider error area; post-auth tenant context (only authorized tenants). Do not make local/development login appear as the production path.
- **API surface:** `GET /api/v1/auth/me` is present in the current API; `POST /api/v1/auth/token` is development-only and must not be presented as a production sign-in contract.
- **States:** Redirecting/authenticating; identity service unavailable; authentication denied; no tenant membership; authorized context loaded.
- **Failure behavior:** Fail closed. No cached prior tenant content is shown after a failed identity or membership refresh.
- **Audit:** Authentication success/failure handling must follow the identity integration's approved audit policy.

### SCR-002 — Tenant overview

- **Features:** F-001, F-010, F-012, F-013. **Roles:** Authorized tenant/platform viewer.
- **Goal:** Summarize only tenant-scoped records and evidence sources that are actually connected.
- **UI:** Application count, route/controller status, telemetry freshness, and recent audit outcomes. Each metric includes source and “as of” timestamp; omit metrics without evidence.
- **API surface:** `GET /api/v1/observability/metrics` reads configured Prometheus data and explicit unavailable metrics. Control API request counters are not inference usage.
- **States:** Loading; verified results; no records; partial source outage; stale telemetry; unauthorized; unavailable.
- **Failure behavior:** Keep source-specific errors visible. Do not render example numbers as real measurements.

### SCR-003 — Applications

- **Features:** F-002. **Roles:** Developer (own registrations), tenant administrator, authorized platform administrator, read-only auditor.
- **Goal:** List and register tenant-owned applications and inspect their truthful provisioning status.
- **Fields:** Name; optional description; environment. Tenant is derived from identity, not editable.
- **Actions:** List, create, inspect. Eligible non-production registrations reveal a credential once; production activation requires a separately approved matching request and reveals a credential only once after catalog provisioning.
- **API surface:** Current `GET/POST /api/v1/applications`, `GET /api/v1/applications/{app_id}`, and `POST /api/v1/applications/{app_id}/lifecycle`.
- **States:** Loading; empty; create form; field validation errors; duplicate/conflict; pending provisioning; observed; failed; forbidden; service unavailable.
- **Audit:** Record successful/failed management mutation according to the durable-audit design; redact credential material.

### SCR-004 — Self-service onboarding

- **Features:** F-003. **Roles:** Tenant members may submit and complete their own requests; tenant administrators review requests.
- **UI:** Request application name, environment, requested model names and quota; show reviewer outcome and completion status.
- **API:** `POST /api/v1/onboarding/requests`, tenant-scoped list, reviewer endpoint and requester-only completion endpoint.
- **States:** Pending review; approved; denied; completed; provisioning failure; already completed.
- **Credential:** Only the requester receives a one-time eligible credential. If the response is lost, the key cannot be recovered; follow key revocation/replacement controls.

### SCR-005 — Models and providers

- **Features:** F-004. **Roles:** Tenant administrator/platform operator can manage within assigned scope; developer and auditor read-only as authorized.
- **Goal:** Maintain an approved provider/model catalog and refer to a credential stored outside the Control API.
- **Fields:** Provider, model identifier, display name, Kubernetes Secret reference. Do not accept or render secret plaintext. Failover/weights are not implied by a catalog entry.
- **Actions:** List, register, inspect. Explain that a Secret reference is not proof that a secret exists or provider is healthy unless that check has been integrated.
- **API surface:** Current `GET/POST /api/v1/models`.
- **States:** Loading; empty; valid/invalid form; duplicate; missing/inaccessible Secret reference; provider health unknown; forbidden; dependency unavailable.
- **Audit:** Record catalog mutation without secret values.

### SCR-006 — Routes and policies

- **Features:** F-005, F-006, partial F-009. **Roles:** Tenant administrator/platform operator can manage assigned test scope; developer/auditor read-only as authorized.
- **Goal:** Validate a supported route and optional OSS regex policy, preview generated resources, submit desired state, and view controller-observed status.
- **Fields:** Resource/route name; path/match; approved backend reference; supported policy fields; target test environment. Validate URL/path and exact pinned CRD schema. Reject unsupported policy fields instead of dropping them silently.
- **Actions:** Edit draft; validate; inspect proposed `Gateway`, `HTTPRoute`, `AgentgatewayBackend`/`AgentgatewayPolicy` resources; submit to Kubernetes API. Do not expose a direct agentgateway admin apply action. Revision history and explicit rollback are available in source; live behavior is unverified.
- **API surface:** `GET/POST /api/v1/routes`, `POST /api/v1/routes/validate`, `POST /api/v1/routes/{route_id}/apply`, and route status read-back are present in source; live Kubernetes/CRD compatibility is unverified.
- **States:** Draft; validating; validation failed; ready to submit; Kubernetes write pending/failed; controller reconciling; observed; rejected; status unavailable; stale observed revision.
- **Status labels:** “Observed active” only when the exact target resource and requested revision have verified controller conditions/read-back. Otherwise pending/unknown/error.
- **Audit:** Record actor, tenant, resource, change summary, request/correlation ID, and outcome; exclude credentials and inference content.

### SCR-007 — MCP governance

- **Features:** F-007. **Roles:** Tenant administrator/platform operator can manage assigned test scope; developer/auditor read-only as authorized.
- **Goal:** Register an MCP endpoint and discover tools from a real server response; store CEL-based per-tool policy intent.
- **Fields:** Server name, HTTPS endpoint, tool and policy. Discovery requires an exact `MCP_ALLOWED_HOSTS` match and external egress controls.
- **Actions:** Register; discover tools; edit a tool policy. The policy is not published to or enforced by agentgateway.
- **API surface:** `/api/v1/mcp/servers`, `/discover`, and `/policy`.
- **States:** Unverified; discovering; discovered; transport error; invalid policy; policy stored but not enforced.
- **Compatibility warning:** No tool-call authorization or `tools/list` filtering behavior is claimed until the gateway integration is implemented and verified.

### SCR-008 — Approvals

- **Features:** F-008. **Roles:** Authorized tenant/platform requesters and separate approvers.
- **UI:** Display request scope, requester, proposal, decision and whether an approved request was applied.
- **API:** `/api/v1/approvals` for tenant-scoped request/list/decision operations.
- **States:** Pending; approved; denied; applied; conflict; unauthorized. A requester cannot decide their own request.
- **Boundary:** Only matching production application activation consumes an approval. Other request types are not automatically executed; no quorum or escalation is implemented.

### SCR-009 — Traces and usage

- **Features:** F-010. **Roles:** Tenant/platform viewers; developers restricted to authorized applications; auditor according to approved role mapping.
- **Goal:** Inspect actual gateway-generated trace metadata and supported usage attributes.
- **Filters:** Time range, trace/request ID, authorized application, model, outcome. Filter values are tenant-scoped server-side.
- **Actions:** Query and inspect safe span metadata. Do not expose prompt/completion bodies by default; do not claim token usage until the real provider/gateway telemetry contains it.
- **API surface:** `GET /api/v1/observability/traces` queries the configured Tempo endpoint. Live trace availability and tenant-scoped gateway data are unverified.
- **States:** Loading; results; empty; partial fields; stale; telemetry backend unavailable; forbidden.
- **Audit/privacy:** Do not store secrets or raw sensitive inference payloads in the UI by default.

### SCR-010 — Budgets and cost

- **Features:** F-011. **Roles:** Tenant readers and tenant administrators.
- **UI:** Configure advisory budget and threshold; render observed spend only when the tenant-scoped Prometheus query returns data. Missing samples remain unknown.
- **API:** `GET/PUT /api/v1/finops/budgets`.
- **States:** Not configured; configured; spend unavailable; query failed. Hard-cap requests are rejected because runtime cost enforcement is unavailable.
- **Reason:** `EnterpriseAgentgatewayBudget` is Enterprise-only; no OSS hard-cap enforcement or simulated spend is claimed.

### SCR-011 — Audit events

- **Features:** F-012. **Roles:** Tenant administrator/platform administrator/auditor, scoped by authorization; developers do not see audit data by default.
- **Goal:** Search durable management events with actor, tenant, timestamp, resource, outcome, and correlation ID.
- **Actions:** Filter and inspect event metadata. Do not label the database hash chain as immutable or offer a signed export; durability and tamper tests are unverified.
- **API surface:** `GET /api/v1/audit/events` reads the SQLAlchemy-backed audit store. This is not a compliance certification; no export operation is promised.
- **States:** Loading; results; empty; unavailable; forbidden; incomplete retention indicator.

### SCR-012 — Runtime status

- **Features:** Partial F-009, F-013. **Roles:** Authorized platform/tenant administrators and read-only auditors.
- **Goal:** Show actual Kubernetes resource/controller conditions and their observation time.
- **Actions:** Read route drift/status only. No force-reconcile button or automatic remediation is implemented.
- **API surface:** Route status and `GET /api/v1/operations/drift` are read-only.
- **States:** Unknown; pending; observed; rejected; stale; Kubernetes/controller unavailable; forbidden.
- **Failure behavior:** Show the resource identity and correlation ID. Never turn missing status into “in sync”.

## Shared error presentation

Errors are shown adjacent to the action that failed and in an accessible page-level summary when needed. Preserve form input where safe. Render a human-readable message, stable error code if returned, correlation ID, and a safe next step. Never display stack traces, secret values, raw upstream response bodies, or false success.
