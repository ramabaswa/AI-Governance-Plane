# Governance Workflow Implementation Scope

**Status:** A–F plus approval/onboarding/MCP/FinOps/policy-history/operations source has been added; runtime and test verification pending.
**Reference baseline:** agentgateway OSS `v1.6.0`, commit `ea5608642b9d5c94c5baf5fd9f2f9849b808e963` (Apache-2.0).  
**Verification status:** Application tests, migrations, Kubernetes integration, and external runtime behavior have not been executed for this handoff.

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
| **A. Authentication and tenant access — F-001** | OIDC JWT verification for configured issuer/audience/JWKS; authorization derives tenant roles from stored memberships, not caller role claims. Local token login is development-only. | OIDC provider interoperability and production configuration are unverified; automated tests are present but unrun. |
| **B. Application registry and credentials — F-002** | SQLAlchemy persistence; eligible applications receive a one-time key stored as a SHA-256 hash and provisioned as a keyHash-only ConfigMap entry. Production activation now requires a separate approved `application_activation` request and provisions its credential only at activation. | Kubernetes ConfigMap write/read semantics and gateway acceptance/removal are unverified. |
| **C. Model/backend registry — F-004** | Persistent model metadata and provider Secret references; credentials are not stored as plaintext model fields. | Provider secret resolution and a real backend call are not implemented/verified in this slice. |
| **D. Routes and supported guardrails — F-005, F-006** | Translator emits Kubernetes Gateway API/agentgateway resources; server-side apply and controller status read-back are used. Unsupported route capabilities are rejected. | Generated CRDs and status conditions have not been validated against a live v1.6.0 installation. |
| **E. Audit and observability — F-010, F-012** | Persistent audit hash-chain service; OTel control-API request instrumentation; Tempo trace and Prometheus metric readers expose explicit unavailable states. | No gateway request/token metrics are fabricated; live trace/metric availability and audit-chain behavior remain unverified. |
| **F. Onboarding and approvals — F-003, F-008** | Durable onboarding requests with reviewer approval and requester-only completion; durable approval requests with self-approval rejection and one-time application of approved production activation. | No quorum, timeout/escalation engine, or generic mutation executor is implemented. |
| **G. MCP governance — F-007** | Tenant-scoped server registry, allowlisted HTTPS `initialize`/`tools/list` discovery, CEL-validated per-tool policy records. | Policies are stored and audited but are not published to or enforced by agentgateway. |
| **H. FinOps — F-011** | Tenant budget configuration and optional tenant-scoped Prometheus estimated-cost observation. | No inference hard cap or cost enforcement; observed costs remain unavailable without a correctly scoped monthly query. |
| **I. Policy lifecycle and operations — F-009, F-013** | Checksummed route revision snapshots, explicit rollback through the Kubernetes apply path, and read-only tenant drift/status observations. | No automatic remediation. Controller semantics, live rollback, and Kubernetes write behavior remain unverified. |

The source does **not** establish end-to-end inference through a live gateway.
Local Compose does not include an agentgateway runtime.

## Explicit feature boundaries

- **Approvals:** persisted request/decision workflow with requester/decider separation; only approved production application activation consumes an approval. Generic approvals do not automatically execute arbitrary policy changes, and no quorum or escalation behavior is claimed.
- **MCP:** discovery is a real outbound HTTPS MCP JSON-RPC operation restricted to exact hosts in `MCP_ALLOWED_HOSTS`. Tool policies are management records only until a verified gateway translation/enforcement path is added. Configure network egress restrictions in addition to the application allowlist.
- **FinOps:** budgets are advisory; no `429`, provider spend cap, or gateway token limit is enforced. Cost is an observed Prometheus value only when a tenant-scoped monthly query is configured. Empty/missing telemetry is not converted to zero.
- **Policy lifecycle:** route snapshots are checksummed, history is tenant-scoped, and rollback creates a new desired revision through the same Kubernetes apply path. This does not guarantee runtime rollback or a successful inference path.
- **Operations:** the drift endpoint reads controller/resource status and never mutates desired state. Automated reconcile/remediation is not implemented.
- No firewall, WAF, NHI platform, autonomous remediation, or additional chained inference proxies.

## Ownership and source of record

| Domain | Owner / source of record | Responsibility and boundary |
|---|---|---|
| **Desired gateway configuration** | Kubernetes `Gateway`, `HTTPRoute`, `AgentgatewayBackend` and `AgentgatewayPolicy` resources authored by the platform API. | These resources are the sole active desired-state record for the gateway. Platform drafts, if persisted, are not a second active configuration source. |
| **Configuration reconciliation** | agentgateway Kubernetes controller. | It reconciles those resources and reports their status. The platform reads that status; it does not also push standalone YAML to an admin endpoint. |
| **Observed runtime configuration** | agentgateway controller/resource status, read from the Kubernetes API. | “Observed active” requires relevant status conditions/read-back, not merely a successful write request. Runtime request outcomes remain agentgateway evidence. |
| **Identity** | Generic OIDC for user authentication; PostgreSQL tenant membership/role mapping for management authorization; agentgateway validates configured workload API-key credentials for runtime access. | A client-supplied tenant header or token role claim is not authority. OIDC provider-specific behavior remains unverified. |
| **Secrets** | Kubernetes Secret store for MVP provider credentials; secret manager remains the owner of plaintext. | Platform records Secret references only. Credentials do not enter generated manifests, API responses, logs, traces, or audit details. External Vault/Purview integration is not in the OSS MVP. |
| **Applications and models** | PostgreSQL (or development SQLite) for registry metadata; Kubernetes resources for active gateway configuration. | Production schema is managed by Alembic; no migration or durability test has been run. |
| **MCP servers/tools** | PostgreSQL registry and allowlisted discovery; per-tool CEL policy records. | No policy is published to the gateway; registry state does not authorize an MCP invocation. |
| **Audit** | SQLAlchemy-backed audit event table with a hash chain. | Durability and tamper-detection tests are present but unrun; this is not a compliance certification. |
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

- The Control API is the only platform writer for platform-managed gateway objects.
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

These remain integration blockers, not test passes. Do not pre-label them complete.
