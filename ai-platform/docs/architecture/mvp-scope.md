# Governance Plane MVP Scope

**Deployment decision:** Azure Container Apps for the Governance Plane and standalone agentgateway; no AKS/Kubernetes dependency in the target architecture.
**Current implementation status:** The business API and persistence source exist, but gateway resource provisioning is still Kubernetes-specific. This repository is not yet a complete ACA deployment or a working ACA-to-agentgateway control plane.

## Product boundary

The Governance Plane is a management and audit system. Agent inference travels through agentgateway and directly to approved model/MCP services. The Plane stores tenant-scoped intent, validates and approves changes, then publishes supported gateway configuration through a private management interface. PostgreSQL is the source of record for Plane workflows; agentgateway's own store/runtime is authoritative for active gateway configuration and observed behavior.

## Selected runtime architecture

| Component | ACA target | Responsibility |
|---|---|---|
| Control API and console | Long-running ACA app with authenticated ingress; APIM may be placed first | User/API entry, tenant authorization, governance workflows, durable desired state |
| Reconciliation worker | Separate long-running internal ACA app, initially one replica | Claim pending outbox records, publish gateway config, read back evidence, retry safely |
| agentgateway | Separate standalone ACA app; private management endpoint; private or APIM-mediated traffic ingress | Runtime authentication, supported gateway policies, routing, provider/MCP egress |
| PostgreSQL | Azure Database for PostgreSQL Flexible Server with private networking | Plane tenant registry, workflows, audit, route/model intent, revision/outbox state |
| Secrets | Azure Key Vault and ACA managed identities | Keep plaintext credentials out of source, Plane DB, and image configuration; use gateway managed identity for Azure OpenAI when applicable |
| Migrations | One-shot ACA Job or deployment pipeline step | Apply Alembic migrations before API/worker revisions receive traffic |
| Telemetry | Azure Monitor/OpenTelemetry; optional existing Tempo/Prometheus | Keep API/worker observability separate from agentgateway request usage |

Use distinct managed identities for the API, worker, and gateway. The API should have only required database/Key Vault permissions. The worker additionally needs access to the private gateway management API. The gateway identity receives only provider/secret permissions required at runtime. The worker must be single-replica until database-backed claiming/leases prevent duplicate publications.

## Agent traffic entry paths

1. `Agent → APIM → private agentgateway ingress → approved model/MCP backend`.
2. `Approved private agent → private agentgateway ingress → the same backend set`.

Path 2 is optional per environment. It must apply the same gateway identity and minimum policy baseline as Path 1. APIM can add enterprise edge controls but cannot be the only authorization layer if direct ingress is enabled. No client may reach managed model/MCP backends through an ungoverned alternate path.

The Control API is not on either inference path. An API success response means desired state was accepted by the Plane. It must not be presented as runtime-active until agentgateway reports the applicable configuration/revision and the runtime path has been verified.

## Feature implementation state

| Capability | Source state | ACA work required |
|---|---|---|
| OIDC authentication and tenant memberships | OIDC/JWKS validation and SQLAlchemy tenant authorization source exist | Configure ACA ingress, production issuer(s), secrets, PostgreSQL identity/networking, and validate with live IdPs |
| Applications, keys, and model registry | Database/API source exists; runtime key provisioning is Kubernetes ConfigMap based | Replace ConfigMap catalog with standalone gateway resource API and a safe credential lifecycle; design Key Vault references for non-Azure providers |
| Route and guardrail publishing | Translator emits Kubernetes Gateway API/agentgateway CRDs | Add release-pinned standalone configuration mapping and management API client; validate effective configuration and runtime request behavior |
| Reconciliation and observed state | Worker retries pending DB rows through Kubernetes client/status | Add transactional outbox, concurrency lease, retry/backoff, standalone API publishing, readback, and idempotency |
| PostgreSQL persistence, audit, approvals, policy history | SQLAlchemy models and migrations exist | Provision Flexible Server privately, execute migrations as a deployment step, configure backup/restore and connection identity |
| MCP registration and discovery | Allowlisted HTTPS discovery and policy-intent records exist | Add ACA egress controls; keep tool policies clearly unenforced until a gateway translation is verified |
| CMDB/ITSM/OpenFGA/OPA/APIM | Target design only or partial records | Implement and test typed adapters, source-of-record rules, identity contracts, and fail modes |
| Telemetry and FinOps | API query/presentation source exists; gateway usage data is not established | Export gateway/ACA telemetry, configure tenant attribution and verify actual usage before showing cost |

## Required cutover work

1. Extend the initial ACA Bicep package (`deploy/azure/container-apps`) beyond API/worker apps to cover private networking, ACA environment, PostgreSQL, AgentGateway, and a one-shot migration job. The checked-in package assumes an existing ACA environment, PostgreSQL database, Key Vault, and images.
2. Define a standalone AgentGateway image/config baseline and private ACA ingress. Pin the image version. Protect management routes from agent traffic and unrelated apps.
3. Implement a separate standalone adapter. It must publish only resource kinds supported by the pinned agentgateway release; it must never write agentgateway's private database tables.
4. Replace Kubernetes key ConfigMaps and generated CRDs with supported standalone resource writes. Preserve tenant scoping, key hashing in the Plane, one-time disclosure, revoke semantics, and audit behavior.
5. Make reconciliation durable and idempotent: record intent/outbox atomically, claim with a lease, publish, read back, record outcome, retry with bounded backoff, and expose pending/failed/observed/runtime-verified as distinct states.
6. Implement Key Vault and managed-identity credential paths. Do not put provider plaintext into Plane records, logs, audit, generated image files, or deployment parameters.
7. Configure ingress: APIM → gateway plus optional direct-private gateway ingress. Enforce network egress so gateway-to-backend is the only inference path.
8. Run migrations and verify ACA health, OIDC, API and worker connectivity, gateway config readback, a real deterministic backend request, credential rejection/revocation, and telemetry attribution.

## Claims and exclusions

- A deployed ACA API is not proof that the app can manage standalone agentgateway. The current writer is still Kubernetes-specific.
- Do not claim runtime enforcement, active routes, key revocation propagation, or request-level audit until verified against the pinned standalone release.
- MCP per-tool policy publication, hard spend caps, autonomous drift repair, CMDB/ITSM synchronization, and generic OpenFGA/OPA/Azure Policy translation are not part of the current validated slice.
- APIM and direct private ingress are target paths, not currently deployed configurations.
- PostgreSQL schema migration, ACA infrastructure, Key Vault integration, live gateway configuration, inference, and telemetry have not been validated in this workspace.
