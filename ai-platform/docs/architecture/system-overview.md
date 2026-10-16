# System Overview

**Status:** Documents the implemented governance source and its intended integration boundary.
**Data-plane reference:** agentgateway OSS `v1.6.0` at commit `ea5608642b9d5c94c5baf5fd9f2f9849b808e963`.  
**Verification status:** Application, migration, Kubernetes, and telemetry paths have not been executed or verified against a live environment. Local Compose does not include agentgateway.

For the target dual-ingress design and system-of-record boundaries, see the [canonical architecture](../../../docs/architect.md). APIM ingress is an architectural target and is not implemented in this repository.

## Architecture boundary

```mermaid
flowchart LR
    User["Platform user"]
    Client["Application / agent"]
    PrivateClient["Approved private agent / application"]
    IdP["OIDC identity provider"]

    subgraph CP["AI Governance Plane — control plane"]
        UI["Existing console"]
        API["FastAPI control API"]
        DB[("PostgreSQL\nregistry, workflows, audit, revisions")]
        TelemetryReader["Tenant-authorized telemetry reader"]
    end

    Kube[("Kubernetes API\nactive desired CRDs + status")]
    Controller["agentgateway Kubernetes controller"]

    APIM["Optional APIM ingress\n(not implemented in this repository)"]

    subgraph DP["agentgateway — data plane"]
        Gateway["Gateway runtime\nAPI key, routes, supported policies"]
    end

    Telemetry[("OTel Collector / Tempo / Prometheus")]
    LLM["Deterministic test LLM backend\nthen approved providers"]
    MCP["MCP test server / approved servers"]
    Secrets["Kubernetes Secret store"]

    User --> UI --> API
    IdP --> API
    API <--> DB
    API -->|"single desired-state write path:\nGateway API + agentgateway CRDs"| Kube
    Kube --> Controller --> Gateway
    Controller -->|"resource status"| Kube
    API -->|"read status only"| Kube
    API -->|"allowlisted MCP discovery only"| MCP
    Secrets --> Gateway

    Client -->|"Path 1: LLM/MCP requests"| APIM
    APIM --> Gateway
    PrivateClient -->|"Path 2: approved direct private ingress"| Gateway
    Gateway --> LLM
    Gateway --> MCP
    Gateway -->|"OTLP traces/metrics"| Telemetry
    Telemetry --> TelemetryReader
    TelemetryReader --> API
    API --> DB
```

**The Control API is not an inference proxy.** It manages identity-scoped resources and reads evidence. The target supports APIM → agentgateway and approved private-client → agentgateway paths. Only the direct agentgateway configuration path is represented by current repository source; APIM has not been integrated. Both paths must converge on the same gateway policies and backends, and direct ingress must not bypass the shared security baseline.

Approval/onboarding records, advisory budgets, MCP registry/policy intent, and
route revisions are persisted by the Control API. MCP discovery is a bounded
management-plane call to an exact allowlisted HTTPS host; stored MCP policies
are not published to the gateway and do not authorize data-plane tool calls.
Operations drift checks are read-only.

## Request sequence (target)

```mermaid
sequenceDiagram
    autonumber
    participant App as Application / agent
    participant GW as agentgateway v1.6.0
    participant Policy as Native gateway policy
    participant Backend as Deterministic test backend
    participant OTel as OTel collector/store

    App->>GW: LLM request with configured workload credential
    GW->>Policy: Validate identity, route and enabled policy
    alt Rejected
        Policy-->>GW: Deny
        GW-->>App: Denial response
    else Allowed
        Policy-->>GW: Allow and select configured backend
        GW->>Backend: Forward request
        Backend-->>GW: Deterministic response and actual usage metadata
        GW->>OTel: Emit trace/metrics if supported
        GW-->>App: Response
    end
```
**The trace/usage branch is a requirement to prove, not an assumed integration.** No model call or gateway enforcement is to be mocked away in the real-gateway integration test.

## Configuration lifecycle (target)

```mermaid
sequenceDiagram
    autonumber
    actor Admin
    participant UI as Console
    participant API as Control API
    participant Store as Platform store
    participant Kube as Kubernetes API
    participant Agw as agentgateway controller

    Admin->>UI: Submit route/model intent
    UI->>API: Versioned, tenant-authorized request
    API->>Store: Record user action and audit event
    API->>API: Validate inputs, increment revision and synthesize pinned CRD shape
    API->>Kube: Create/update Gateway API and agentgateway resources
    Kube-->>API: Write accepted or error
    API-->>UI: Pending controller observation (not active success)
    Agw->>Kube: Watch desired resources
    Agw->>Agw: Reconcile runtime
    Agw->>Kube: Publish resource status/conditions
    API->>Kube: Read observed status

    alt Current revision is accepted and route references are resolved
        API->>Store: Record observed result and audit evidence
        API-->>UI: Observed active
    else Rejected, stale revision, or unavailable
        API->>Store: Record explicit failure or pending evidence
        API-->>UI: Failed or still pending - retain diagnostic correlation
    end
```

The source maps `Accepted=True` on all generated resources and
`ResolvedRefs=True` on the `HTTPRoute` to `observed_active`; a false
`Accepted`/`ResolvedRefs` condition maps to `rejected`, and absent conditions or
a stale route revision remain `pending`. A write acknowledgement is not an
observation. Live v1.6.0 CRD compatibility and controller condition behavior
remain unverified. This path deliberately excludes a second GitOps writer and
the existing unverified direct `/config/apply` HTTP assumption.

## Ownership summary

| Concern | Owner |
|---|---|
| User credentials and primary identity | Configured generic OIDC provider |
| Tenant membership and platform roles | Control-plane database |
| Logical gateway desired state | Platform API; active desired resources stored as Kubernetes Gateway API/agentgateway CRDs |
| Runtime reconciliation and observed resource status | agentgateway controller, surfaced through Kubernetes resource status |
| Provider secrets | Kubernetes Secret store; platform keeps references |
| Audit events | Control-plane database with hash-chain records |
| Request usage/traces | OTel Collector, Tempo and Prometheus are configured; gateway usage is not yet verified |
| Approval decisions | SQLAlchemy-backed approval requests; only production application activation consumes an approved request. |

## Current workspace surfaces and limits

The active API surfaces are implemented in source but are not proof of production behavior:

| Existing router prefix | Operations observed in source | Current limitation observed |
|---|---|---|
| `/api/v1/auth` | OIDC-backed identity and development-only local login | Provider configuration and identity lifecycle are unverified. |
| `/api/v1/tenants` | Tenant membership administration | Authorization and database integration tests are present but unrun. |
| `/api/v1/applications` | Persistent application registry, key issue/status/revoke | Kubernetes key catalog updates and gateway runtime acceptance are unverified. |
| `/api/v1/models` | Persistent model/backend registry | Provider secrets are references; no inference request is proxied by this API. |
| `/api/v1/routes` | Validate, synthesize, apply and read observed Kubernetes resources | CRD compatibility and live controller status have not been verified. |
| `/api/v1/audit` | Tenant-scoped audit evidence | Persistence and chain verification have not been tested in this handoff. |
| `/api/v1/observability` | Tempo traces and configured Prometheus metrics | Gateway request/token metrics are explicit unavailable values unless configured and emitted. |

Approval, onboarding, MCP registry/discovery, budget, read-only operations, and
policy revision routes are mounted. MCP policy records are not published to
the gateway, budget enforcement is advisory, and drift checks do not remediate.
The Kubernetes client no longer calls a direct `/config/apply` endpoint, and a
Kubernetes write acknowledgement alone is not reported as controller-observed
active state.

## Source and status references

- The pinned source, lab source files and OSS/Enterprise distinctions are recorded in [source-inventory.md](../references/source-inventory.md).
- Feature-level evidence, adaptation needs and verification state are recorded in [feature-source-matrix.md](../references/feature-source-matrix.md).
- Stable identifiers F-001 through F-013 are retained from the wireframe coverage matrix; see [MVP scope](mvp-scope.md) for active source and explicit enforcement gaps.
- Tests have not been executed. See [test traceability](../features/test-traceability.md) for coverage mapped to current test files.
