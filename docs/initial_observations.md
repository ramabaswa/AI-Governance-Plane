# Initial Architecture Observations

**Purpose:** Capture the architecture decisions and open questions from the review of AI-Governance-Plane, agentgateway, and the Agentgateway/APIM articles discussed on 2026-10-16.

## Executive view

AI-Governance-Plane is best positioned as an enterprise management and governance control plane alongside agentgateway. It should manage agent and backend registration, identity and ownership metadata, approvals, policy intent, configuration revisions, audit evidence, and operational visibility. agentgateway remains the runtime data plane that receives and enforces agent traffic.

The platform should have two supported ingress paths that converge on the same agentgateway runtime:

1. **APIM path:** agent or application → Azure API Management (APIM) → agentgateway → approved model/MCP backends.
2. **Direct path:** approved private/internal agent or application → agentgateway → the same approved backends.

The direct path must not be an ungoverned bypass. Both paths need a common minimum runtime security baseline at agentgateway, with APIM adding enterprise-edge capabilities on the first path. Neither path should route around agentgateway to reach model providers or MCP servers directly.

## Findings and decisions

### Product and control-plane boundary

- The Control API should not proxy inference. It manages intent and platform records; it is outside the normal LLM/MCP request path.
- The Kubernetes API and agentgateway Kubernetes controller are the selected configuration delivery and reconciliation path in this repository. The platform writes supported Kubernetes Gateway API and agentgateway resources, then reads controller status. A successful API write is not proof that a configuration is active.
- Keep one authoritative active desired state for each platform-managed gateway object. Avoid simultaneous uncoordinated writers from the platform and GitOps. If GitOps is introduced, define ownership and conflict behavior explicitly.
- The governance plane and agentgateway are complementary components. The governance plane is not a replacement for the gateway, and agentgateway does not supply the enterprise system-of-record workflows by itself.

### Two ingress paths

| Path | Intended use | Responsibilities |
|---|---|---|
| APIM → agentgateway | Enterprise-published APIs, external/partner access, or traffic that needs APIM’s API lifecycle and edge controls. | APIM can provide API publication/catalog integration, enterprise authentication integration, edge quotas/rate limits, and gateway-level observability. agentgateway remains responsible for its supported AI/MCP-aware routing and runtime policies. |
| Direct → agentgateway | Approved private workload traffic where an APIM hop is not required. | agentgateway must still authenticate and authorize the workload, apply the common required route/policy baseline, and emit runtime evidence. Network policy should restrict this path to approved callers. |

For both paths, use the same agentgateway-managed backends and baseline policies. Decide explicitly whether APIM forwards the caller token or exchanges it for a gateway-facing identity; validate issuer, audience, claims, and identity propagation at each hop. Prevent a less-secure direct route from bypassing requirements imposed on APIM traffic. Keep rate limits, quotas, and audit responsibility clear so that duplicate layers do not give conflicting answers.

### Identity and systems of record

- Entra ID, Okta, or another OIDC provider is authoritative for authentication. Do not make provider-specific environment variables the identity model. Use a provider-neutral configuration record per environment (issuer, audience/client identifiers, JWKS/discovery settings, allowed algorithms, and secret references), then add provider-specific settings only when actually needed.
- Identify a user by the pair `(issuer, subject)`, not by email or `subject` alone. The current workspace has issuer-scoped membership records; provider interoperability and production setup still need environment validation.
- Tenant membership and platform roles are authorization records owned by AI-Governance-Plane unless an external authorization service is explicitly adopted.
- CMDB should be the source of record for enterprise agent/application identity, owner/team, business service, environment, and lifecycle attributes. The plane can synchronize or reference those records and retain a stable CMDB identifier; avoid an independently editable duplicate that silently becomes authoritative.
- ITSM should remain the source of record for change tickets and approval evidence when the enterprise process requires it. Store ticket identifiers and decision references in the plane; make the platform workflow enforce required approvals before applying protected changes.
- Azure Policy governs Azure resource compliance. It is not a substitute for runtime authorization of every agent request.

### Policy-as-code layers

Do not model OpenFGA, OPA, Azure Policy, and agentgateway as interchangeable policy engines. Treat policy configuration as typed, versioned references with an explicit owner and enforcement point.

| Technology / layer | Appropriate responsibility | How the plane should relate to it |
|---|---|---|
| OpenFGA | Relationship and tuple-based authorization, such as whether a team owns or may administer an agent. | Store the model/store reference and manage or query relationships through an adapter if selected. Do not assume agentgateway can consume arbitrary OpenFGA models directly. |
| OPA | General-purpose policy decisions using Rego, including a possible external policy decision service. | Register policy bundle/service references and decision contracts. Integrate through a supported gateway external-authorization mechanism or an application/control-plane decision point. |
| Azure Policy | Compliance of Azure resources and deployments. | Reference assignment/scope/compliance evidence for infrastructure governance. It is not a per-request LLM/MCP decision engine. |
| agentgateway policies | Supported request-time gateway behavior such as authentication/authorization, routing, rate limiting, and supported prompt/MCP controls. | The plane validates and translates only capabilities supported by the pinned agentgateway API/version, publishes through Kubernetes, and reports controller-observed status. |

The environment configuration should declare which policy systems are enabled, their endpoints/IDs and secret references, which policy types apply, and the enforcement point. It should not flatten unrelated policy languages into one ambiguous policy document. The plane must distinguish `configured`, `published`, `accepted`, and `runtime-verified` states. A stored policy record is not enforcement: in this workspace, MCP tool policies are recorded but are not published to or enforced by agentgateway.

### Agentgateway and API integration

- The repository currently integrates with agentgateway through Kubernetes resources and controller status; it does not call an assumed direct configuration endpoint.
- “No OpenAPI integration” is too broad. Upstream agentgateway standalone configuration documents OpenAPI-to-MCP tool exposure. The Kubernetes CRD surface targeted by this repo/pinned version must be checked separately; the current platform translator has no OpenAPI-to-MCP configuration model. Ordinary HTTP routing to an OpenAPI service is not the same as converting its operations into MCP tools.
- Validate generated resources against the exact installed CRDs and controller before claiming support. The repo pins agentgateway OSS v1.6.0, but the docs and source reviewed here say live Kubernetes compatibility and runtime behavior have not been verified.
- MCP discovery in the current code is a bounded management-plane HTTPS operation against allowlisted hosts. The discovery allowlist is not a runtime network boundary; enforce egress restrictions at the network layer as well.

### Current implementation state from repository review

- Present in source: OIDC authentication and issuer-scoped memberships, tenant/application/model registries, approval/onboarding flows, route intent translation to Kubernetes resources, reconciliation/status read-back, audit and telemetry surfaces, MCP registry/discovery, budget records, and policy revision history.
- Not established as end-to-end runtime behavior: live agentgateway CRD compatibility, a real inference request through the gateway, runtime key acceptance, gateway telemetry availability, MCP policy publication/enforcement, and hard budget enforcement.
- APIM is not currently an implemented traffic hop in this repository. The two-path design is an architecture target; integration work must add APIM configuration/identity/observability ownership and test both paths.
- A2A integration and a full external CMDB/ITSM/OpenFGA/OPA/Azure Policy connector are not established by the current source surfaces reviewed.
- A database hash chain is useful audit evidence but is not, by itself, immutable storage or a compliance certification. Stronger evidence requirements may call for external anchoring or WORM storage.

## Recommended configuration model

Keep environment-specific configuration separate from agent and policy intent:

1. **Environment/integration registry:** environment identifier; Kubernetes cluster/namespace; pinned gateway release and supported API capabilities; ingress modes enabled; OIDC provider records; CMDB/ITSM endpoints and secret references; policy-engine connections; telemetry destinations; secret-manager references.
2. **Agent/application record:** stable internal ID and source-system IDs; owner/team; environment; lifecycle; approved backend/tool references; allowed ingress path(s); workload identity reference.
3. **Versioned desired configuration:** routes and gateway-supported runtime policy references, with approval and audit linkage.
4. **Observed state:** Kubernetes resource generation and controller conditions, plus separately reported traffic/telemetry evidence. Never collapse desired and observed state into one status.

Environment variables should carry deployment bootstrap values (database URL, OIDC discovery configuration, Kubernetes connection settings, secret references, telemetry endpoints), not become the durable inventory of all providers, agents, and policies. Secret values belong in a secret manager; the plane and generated resources should carry references where supported.

## Decisions still needed

- Which classes of agents may use APIM and which may use the direct private path? Is APIM optional per environment, per API, or per application?
- What authentication/token exchange contract applies between APIM and agentgateway? Which caller identity must be visible to gateway policies and audit logs?
- Which system owns the authoritative agent catalog: CMDB, a dedicated agent registry, or CMDB plus a synchronized platform projection?
- Which ITSM approval states are mandatory before creating/changing production routes, policies, backends, or MCP access?
- Which policy engine is authoritative for each decision type, and how will each be called/enforced at runtime?
- Which pinned agentgateway Kubernetes release/API can express required OpenAPI-to-MCP behavior, external authorization, and MCP tool policies?
- What telemetry fields and evidence-retention guarantees are required for both ingress paths?

## References

- [Canonical target architecture](architect.md)
- [Repository system overview](../ai-platform/docs/architecture/system-overview.md)
- [Repository MVP scope and implementation limits](../ai-platform/docs/architecture/mvp-scope.md)
- [agentgateway standalone OpenAPI integration](https://agentgateway.dev/docs/standalone/latest/integrations/mcp/servers/openapi/)
- [agentgateway Kubernetes API reference](https://agentgateway.dev/docs/kubernetes/latest/reference/api/)
- [agentgateway Kubernetes MCP documentation](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/)
- [Agentgateway: AI Gateway with a Difference](https://medium.com/@krishnan.srm/agentgateway-ai-gateway-with-a-difference-fbb812545e93)
- [Agentgateway for MCP Implementation](https://medium.com/@krishnan.srm/agentgateway-for-mcp-implementation-cb5fe744df08)
- [APIM as Gateway for MCP](https://medium.com/@krishnan.srm/apim-as-gateway-for-mcp-1-7a528868f7ff)
- [Building Enterprise LLM Guardrails with APIM and Azure AI Content Safety](https://medium.com/@krishnan.srm/building-enterprise-llm-guardrails-with-azure-api-management-azure-ai-content-safety-and-ai-93aa9f386cd7)
- [APIM for Agentic Development](https://medium.com/@krishnan.srm/apim-for-agentic-development-617d62053132)
- [Agentgateway in the World of Agentic Development](https://medium.com/@krishnan.srm/agentgateway-in-the-world-of-agentic-developement-eb02393af8f9)
- [Agentgateway in the World of Agentic Development, Part 2](https://medium.com/@krishnan.srm/agentgateway-in-the-world-of-agentic-developement-2-90c764572de5)
