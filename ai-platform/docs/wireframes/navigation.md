# Navigation and Information Architecture

**Phase:** 2 — Gate 2-approved design baseline  
**Baseline:** Source feature set and known runtime limitations in [MVP scope](../architecture/mvp-scope.md).
**Important:** Navigation visibility is a UX aid, not an authorization boundary. Every operation must be authorized by the Control API against the authenticated user's tenant and role.

## Global frame

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ AI Governance Plane     Tenant: [authorized tenant]     User / role      │
│ Runtime status: [Unknown | Pending | Observed | Degraded]                │
├───────────────────┬────────────────────────────────────────────────────┤
│ MANAGEMENT        │ Screen title                          Help / status │
│ Overview          │                                                    │
│ Applications      │ Content, filters, empty/loading/error states       │
│ Models & providers│                                                    │
│ Routes & policies │                                                    │
│                   │                                                    │
│ EVIDENCE          │                                                    │
│ Traces / usage    │                                                    │
│ Audit events      │                                                    │
│ WORKFLOWS         │                                                    │
│ Onboarding        │                                                    │
│ Approvals         │                                                    │
│ Budgets           │                                                    │
│ Policy revisions  │                                                    │
│ Operations        │                                                    │
│ MCP governance    │                                                    │
└───────────────────┴────────────────────────────────────────────────────┘
```

The active tenant is selected by authenticated identity/membership. A tenant switcher may list only tenants the user is authorized to access; it must not accept arbitrary tenant IDs as authority. The gateway-status indicator is derived from a real controller/status source or displays **Unknown**. It is never hard-coded to “Active”.

## Screen map

| Screen ID | Navigation label | Feature IDs | MVP disposition |
|---|---|---|---|
| `SCR-001` | Sign in | F-001 | In scope; generic OIDC is implemented, provider-specific behavior is unverified. |
| `SCR-002` | Overview | F-001, F-010, F-012, F-013 | In scope as a tenant-scoped summary; only verified telemetry/audit/status facts are shown. |
| `SCR-003` | Applications | F-002 | In scope. |
| `SCR-004` | Onboarding wizard | F-003 | Source workflow; live provisioning and recovery are unverified. |
| `SCR-005` | Models & providers | F-004 | In scope. |
| `SCR-006` | Routes & policies | F-005, F-006, F-009 | Source supports route revisions/rollback; live behavior is unverified. |
| `SCR-007` | MCP governance | F-007 | Source supports allowlisted discovery and stored policy intent; no gateway enforcement. |
| `SCR-008` | Approvals | F-008 | Durable request/decision source workflow; only production application activation consumes approvals. |
| `SCR-009` | Traces & usage | F-010 | In scope only for actual, queryable gateway telemetry; unsupported usage fields are omitted. |
| `SCR-010` | Budgets & cost | F-011 | Advisory budget source workflow; spend is conditional on Prometheus; hard cap unavailable. |
| `SCR-011` | Audit events | F-012 | In scope for tenant-scoped management events; persistence exists in source, but signing/export claims require separate verification. |
| `SCR-012` | Runtime status | F-013 | Read-only route status/drift observations; no automated remediation. |

## Role-oriented access proposal

Roles are UI capabilities, not a substitute for authenticated authorization.
The server-side permission mapping is defined in the authorization module;
OIDC role claims do not override persisted tenant membership. Navigation visibility does not imply runtime integration or verified behavior.

| Screen / operation | `platform_admin` | `tenant_admin` | `developer` | `auditor` |
|---|---|---|---|---|
| `SCR-001` Sign in | Authenticate | Authenticate | Authenticate | Authenticate |
| `SCR-002` Overview | Read authorized tenant/platform scope | Read own tenant | Read own authorized app summary | Read authorized audit/summary scope |
| `SCR-003` Applications | Manage within assigned platform scope | Manage own tenant | Register/read own applications | Read-only authorized scope |
| `SCR-004` Onboarding | Review | Review | Submit/complete own request | Not available |
| `SCR-005` Models & providers | Manage platform scope | Manage own tenant catalog | Read own tenant catalog | Read-only authorized scope |
| `SCR-006` Routes & policies | Manage assigned scope | Manage own tenant in non-production MVP | Read-only | Read-only |
| `SCR-007` MCP governance | Manage assigned scope | Manage own tenant | Read authorized scope | Read-only authorized scope |
| `SCR-008` Approvals | Decide authorized requests | Decide own-tenant requests | Create/read authorized requests | Read authorized scope |
| `SCR-009` Traces & usage | Read authorized scope | Read own tenant | Read only own application scope | Read only authorized scope |
| `SCR-010` Budgets & cost | Read/manage assigned scope | Read/manage own tenant | Read authorized scope | Read-only authorized scope |
| `SCR-011` Audit events | Read authorized scope | Read own tenant | No access by default | Read authorized scope |
| `SCR-012` Runtime status | Read status for assigned scope | Read own tenant status | No access by default | Read-only authorized scope |

Route and MCP policy intent do not imply MCP gateway enforcement. Production applications require approval and one-time key provisioning, but runtime traffic observation remains separate and unverified.

## Navigation and status behavior

- On initial load, show identity resolution and authorized tenant context before displaying tenant data.
- If identity/tenant context cannot be established, render an access error and no tenant data.
- A missing or unreachable status source is **Unknown/Unavailable**, not healthy.
- MCP policy records say they are not gateway-enforced; budget displays never imply a runtime cap; operations remain read-only.
- Every sample value in the clickable prototype is marked as illustrative; no screen implies a live connection.
