# Governance Workflow Implementation Scope

**Status:** A–F plus approval/onboarding/MCP/FinOps/policy-history/operations source is present; automated test suite passes, while live integration behavior remains unverified.
**Reference baseline:** agentgateway OSS `v1.6.0`, commit `ea5608642b9d5c94c5baf5fd9f2f9849b808e963` (Apache-2.0).  
**Verification status:** Full Python suite: **103 passed, 2 skipped**. The PostgreSQL migration, live Kubernetes/CRD behavior, gateway inference, APIM, and gateway telemetry have not been verified.

## Product boundary

The platform is the management/control plane for users, tenant authorization,
application/model registries, approval and onboarding workflows, desired
configuration, audit, and telemetry presentation. agentgateway remains the
runtime data plane. This implementation does not proxy inference.

The Control API does not proxy inference requests. It may manage resources through the Kubernetes API and query selected management/telemetry systems; neither operation belongs in the inference path.

## Pinned upstream and compatibility gates

The latest release tag returned by the agentgateway repository on 2026-10-15 was `v1.6.0`. At that tag, source and tests confirm:

- Standalone model/provider configuration (`examples/llm-basic/config.yaml`).
- MCP JWT and CEL authorization (`examples/mcp-authorization/config.yaml`, `crates/agentgateway/src/mcp/rbac.rs`).
- Regex prompt-guard configuration (`examples/llm-prompt-guard/config.yaml`).
- Kubernetes backend/policy API types and schema tests.
- OTLP trace export configuration (`examples/llm-telemetry/tracing/otel.yaml`).

The pin is a translation target, not proof that the current platform resources are compatible. The following must be demonstrated before gateway integration is treated as delivered:

1. Build/install the actual OSS release and apply the platform-generated resources in an isolated Kubernetes environment.
2. Execute an LLM request through the real gateway to a deterministic test backend, with the platform API absent from that request path.
3. Confirm JWT/API-key authorization, request routing and configured OSS regex policy at that gateway version.
4. Confirm what usage/token attributes are emitted for the chosen provider/backend, then connect a telemetry store and prove queryability.

If any required capability fails a compatibility gate, stop and bring the exact gap back for scope approval. Do not silently switch to Enterprise CRDs, mocks, or a different release.
MCP discovery and policy management are implemented as control-plane source;
runtime MCP policy publication/enforcement remains a compatibility and
integration gap.

### Enterprise features explicitly excluded

The official Enterprise comparison and lab manifests identify `EnterpriseAgentgatewayBudget`/`entBudgetEnforcement` as Enterprise capabilities. The Enterprise `entPromptGuard` variant adds Purview DLP. The OSS MVP therefore makes **no hard-budget, cost-enforcement, Purview, or Enterprise management-UI claim**. The virtual-key lab's spend test uses a deterministic mock LLM and artificial prices; that is not evidence of provider spend or OSS budget support.

## Implemented source scope

The code contains the following initial control-plane slice. “Implemented” here
means source code and tests are present; it does not mean the service, schema,
gateway, or telemetry has been executed or integrated successfully.

| Outcome / stable feature IDs | Current implementation | Verification boundary |
|---|---|---|
| **A. Authentication and tenant access — F-001** | OIDC JWT verification for configured issuer/audience/JWKS; authorization derives tenant roles from memberships keyed by issuer, subject, and tenant, not caller role claims. Local token login is development-only. | Automated tests pass; production provider interoperability is unverified. Issuer migration requires an explicitly configured legacy issuer and has not run against PostgreSQL. |
| **B. Application registry and credentials — F-002** | SQLAlchemy persistence; eligible applications receive a one-time key stored as a SHA-256 hash and provisioned as a keyHash-only ConfigMap entry. Production activation now requires a separate approved `application_activation` request and provisions its credential only at activation. | Kubernetes ConfigMap write/read semantics and gateway acceptance/removal are unverified. |
| **C. Model/backend registry — F-004** | Persistent model metadata and provider Secret references; credentials are not stored as plaintext model fields. A tenant-authorized capabilities endpoint reports the pinned translator's supported providers; the Console excludes unsupported providers from route selection. | Provider secret resolution and a real backend call are not implemented/verified in this slice; non-Console clients still rely on route validation to reject unsupported providers. |
| **D. Routes and supported guardrails — F-005, F-006** | Translator emits validated-subset Kubernetes Gateway API/agentgateway resources; server-side apply and controller status read-back are used. Unsupported route capabilities are rejected before persistence. | Generated CRDs and status conditions have not been validated against a live v1.6.0 installation; observed resource acceptance is not runtime request verification. |
| **E. Audit and observability — F-010, F-012** | Persistent audit hash-chain service; OTel control-API request instrumentation; Tempo trace and Prometheus metric readers expose explicit unavailable states. | Automated tests pass; no gateway request/token metrics are fabricated. Live telemetry export/query and external audit anchoring remain unverified/not implemented. |
| **F. Onboarding and approvals — F-003, F-008** | Durable onboarding requests with reviewer approval and requester-only completion; durable approval requests with self-approval rejection and one-time application of approved production activation. | No quorum, timeout/escalation engine, or generic mutation executor is implemented. |
| **G. MCP governance — F-007** | Tenant-scoped server registry, allowlisted HTTPS `initialize`/`tools/list` discovery, CEL-validated per-tool policy records. | Policies are stored and audited but are not published to or enforced by agentgateway. |
| **H. FinOps — F-011** | Tenant budget configuration and optional tenant-scoped Prometheus estimated-cost observation. | No inference hard cap or cost enforcement; observed costs remain unavailable without a correctly scoped monthly query. |
| **I. Policy lifecycle and operations — F-009, F-013** | Checksummed route revision snapshots, explicit rollback through the Kubernetes apply path, read-only tenant drift/status observations, and a database-backed worker retrying stale pending route applies. | Worker has no durable per-attempt record, multi-worker claim/lease, or exponential backoff; no deletion cleanup or drift remediation. Controller semantics and live rollback remain unverified. |

The source does **not** establish end-to-end inference through a live gateway.
Local Compose does not include an agentgateway runtime.

## Explicit feature boundaries

- **Approvals:** persisted request/decision workflow with requester/decider separation; only approved production application activation consumes an approval. Generic approvals do not automatically execute arbitrary policy changes, and no quorum or escalation behavior is claimed.
- **MCP:** discovery is a real outbound HTTPS MCP JSON-RPC operation restricted to exact hosts in `MCP_ALLOWED_HOSTS`. Tool policies are management records only until a verified gateway translation/enforcement path is added. Configure network egress restrictions in addition to the application allowlist.
- **FinOps:** budgets are advisory; no `429`, provider spend cap, or gateway token limit is enforced. Cost is an observed Prometheus value only when a tenant-scoped monthly query is configured. Empty/missing telemetry is not converted to zero.
- **Policy lifecycle:** route snapshots are checksummed, history is tenant-scoped, and rollback creates a new desired revision through the same Kubernetes apply path. This does not guarantee runtime rollback or a successful inference path.
- **Operations:** the drift endpoint reads controller/resource status and never mutates desired state. A separate worker retries persisted stale `pending` applies and records observed status; it is not a general desired-state reconciler and has no durable attempt ledger, concurrency claim, exponential backoff, delete cleanup, or drift remediation.
- **Environment configuration:** OIDC providers and selected endpoints/targets are supplied through environment/bootstrap configuration. A durable, typed environment/integration registry has not been implemented; the provider-neutral target record is specified in the [canonical architecture](../../../docs/architect.md).
- No firewall, WAF, NHI platform, autonomous remediation, or additional chained inference proxies.

## Ownership and source of record

| Domain | Owner / source of record | Responsibility and boundary |
|---|---|---|
| **Desired gateway configuration** | Kubernetes `Gateway`, `HTTPRoute`, `AgentgatewayBackend` and `AgentgatewayPolicy` resources authored by the Control API and its same-workflow recovery worker. | These resources are the sole active desired-state record for the gateway. The worker retries the same database-backed route revision using the shared translator; it is not an independent configuration owner. |
| **Configuration reconciliation** | agentgateway Kubernetes controller. | It reconciles those resources and reports their status. The platform reads that status; it does not also push standalone YAML to an admin endpoint. |
| **Observed runtime configuration** | agentgateway controller/resource status, read from the Kubernetes API. | “Observed active” requires current-generation status conditions and matching managed revision labels, not merely a successful write request. Runtime request outcomes remain agentgateway evidence. |
| **Identity** | Generic OIDC for user authentication; PostgreSQL tenant membership/role mapping for management authorization; agentgateway validates configured workload API-key credentials for runtime access. | A client-supplied tenant header or token role claim is not authority. OIDC provider-specific behavior remains unverified. |
| **Secrets** | Kubernetes Secret store for MVP provider credentials; secret manager remains the owner of plaintext. | Platform records Secret references only. Credentials do not enter generated manifests, API responses, logs, traces, or audit details. External Vault/Purview integration is not in the OSS MVP. |
| **Applications and models** | PostgreSQL for registry metadata; Kubernetes resources for active gateway configuration. | ORM/API behavior is covered by the automated suite; production PostgreSQL schema migration and durability have not been verified. |
| **MCP servers/tools** | PostgreSQL registry and allowlisted discovery; per-tool CEL policy records. | No policy is published to the gateway; registry state does not authorize an MCP invocation. |
| **Audit** | SQLAlchemy-backed audit event table with a hash chain. | Automated tests pass; production durability and external immutable anchoring are unverified/not implemented. This is not a compliance certification. |
| **Usage and traces** | OTel Collector/Tempo and Prometheus are configured as readers/export targets; the platform is a tenant-authorized reader/presenter. | Control API metrics are distinct from inference usage. Gateway token/cost fields are unavailable until actual telemetry is integrated. |
| **Approvals** | PostgreSQL approval-request ledger and audited decisions. | Only production application activation is wired to consume an approved request; other approval types are records only. |
| **Budgets** | PostgreSQL budget policy and configured tenant-scoped Prometheus query. | No hard-cap enforcement; spend is unknown if source/query is absent. |
| **Policy history** | PostgreSQL route snapshots with SHA-256 checksums. | Database-backed history is not immutable; rollback requires a valid Kubernetes write and controller observation. |

## Single configuration write path

**Selected path: Kubernetes CRD/controller-managed configuration.**

```text
Console → versioned Control API → validate/authenticate → Kubernetes API writes CRDs
                                                    ↓
                                      agentgateway controller
                                                    ↓
                                         gateway runtime
                                                    ↓
                           controller status read back by platform
```

- The Control API and its recovery worker are components of one platform writer workflow for platform-managed gateway objects.
- The agentgateway controller is the only runtime reconciler for those resources.
- GitOps is not an additional writer for the same managed objects in this MVP.
- The platform does not call an assumed `/config/apply` endpoint and does not run a second standalone-YAML reconciliation path.
- A rejected or partial Kubernetes/controller reconcile is reported as failed/pending, never success-shaped completion.

The implementation uses the Kubernetes API path. It does not use the prior direct `/config/apply` admin endpoint. Live controller reconciliation remains unverified.

## Release-readiness blockers before integration claims

1. Provision production OIDC, PostgreSQL, and telemetry endpoints and migrate the database.
2. Verify OSS v1.6.0 Kubernetes installation/API permissions and generated resource compatibility.
3. Confirm runtime key catalog behavior and gateway credential identity binding.
4. Add a deterministic end-to-end gateway/backend environment before claiming inference routing or enforcement.
5. Verify MCP host allowlisting and egress protections; verify that the gateway enforcement path is implemented before claiming tool-policy enforcement.
6. Deploy both ingress paths only after proving that APIM and approved direct workloads enforce the same minimum gateway identity/policy baseline; neither path is currently deployed by this repository.
7. Implement typed CMDB/ITSM/policy-engine adapters and source-of-record conflict/failure rules before presenting those systems as connected.

These remain integration blockers, not test passes. Do not pre-label them complete.
