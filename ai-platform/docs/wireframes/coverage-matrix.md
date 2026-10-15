# Wireframe and Feature Coverage Matrix

**Phase:** 2 — Gate 2-approved design baseline  
**Status:** This is a design map, not an implementation inventory. Current source scope is A–F; MCP, approvals, onboarding, budgets, and automated drift remediation are deferred. See [MVP scope](../architecture/mvp-scope.md) and [test traceability](../features/test-traceability.md) for current implementation and verification status.

| Feature ID | Feature | Primary screen | Journey | MVP disposition | UX/API acceptance focus | Current evidence status |
|---|---|---|---|---|---|---|
| **F-001** | Tenant & identity scoping | `SCR-001`, global frame | A | In scope | Resolve user/tenant before data; enforce tenant boundary server-side; deny safely on missing context. | OIDC and persisted memberships exist in source; provider integration is unverified. |
| **F-002** | Application & agent registry | `SCR-003` | A | In scope | Register in authorized tenant; show truthful lifecycle; production drafts receive no key while approvals are deferred. | Persistent registry and hashed key catalog exist in source; live gateway binding is unverified. |
| **F-003** | Self-service onboarding | `SCR-004` | — | Deferred | Mark not available in MVP; no key/model/quota provisioning simulation. | No verified platform onboarding flow. |
| **F-004** | Approved model/backend catalog | `SCR-005` | A | In scope | Record approved provider/model and Secret reference; never expose secret plaintext; show unverified provider health as unknown. | Persistent catalog exists in source; pinned gateway schema compatibility is unverified. |
| **F-005** | Gateway routes and traffic policy | `SCR-006` | A, B | In scope | Validate and preview declarative resources; write through Kubernetes API; wait for controller read-back. | Kubernetes translator/apply/status path exists in source; live CRD compatibility is unverified. |
| **F-006** | OSS regex guardrails | `SCR-006` | B | Narrow in-scope option | Limit choices to verified OSS schema and supported regex semantics; state that semantic DLP/Purview is excluded. | Upstream example inspected; platform integration and end-to-end enforcement are unverified. |
| **F-007** | MCP server/tool governance | `SCR-007` | — | Deferred | No active MCP workflow or API; do not present simulated discovery or invocation. | Not mounted in the active API. |
| **F-008** | HITL policy approvals | `SCR-008` | — | Deferred | Disabled/not available; no simulated reviewer decision or production path. | Lab uses custom service; no native platform approval product. |
| **F-009** | Policy lifecycle and rollback | `SCR-006`, `SCR-012` | B | Partial | Show desired, API-accepted, controller-observed and failure states; no rollback action in MVP. | Kubernetes status read-back exists in source; live controller semantics are unverified. |
| **F-010** | Traces and usage | `SCR-002`, `SCR-009` | A | In scope, evidence-dependent | Tenant-scope real telemetry; distinguish missing fields from zero; label time window and source. | Tempo/Prometheus readers and OTel API instrumentation exist in source; gateway usage is unverified. |
| **F-011** | FinOps, budgets and cost | `SCR-010` | — | Deferred | Mark unavailable; no hard caps, provider spend estimates, or budget progress simulation. | Budget CRD is Enterprise-only; lab uses simulated spend. |
| **F-012** | Audit evidence | `SCR-002`, `SCR-011` | A, B | In scope, durability required | Show actor, tenant, event, resource, outcome and correlation ID; redact secrets; clearly label storage/signing guarantees. | Persistent hash-chain implementation exists in source; durability and tamper tests are unrun. |
| **F-013** | Operational status and drift | `SCR-002`, `SCR-012` | — | Deferred automation | No automated drift remediation; route status reads are limited to the F-005 surface. | No separate drift automation is implemented. |

## Screen-to-feature coverage

| Screen ID | Screen | Feature IDs | Main UX states |
|---|---|---|---|
| `SCR-001` | Sign in and tenant context | F-001 | Resolving, signed in, unauthorized, identity service unavailable |
| `SCR-002` | Tenant overview | F-001, F-010, F-012, F-013 | Loading, verified data, empty, partial data, stale, unavailable |
| `SCR-003` | Applications | F-002 | Loading, empty, create validation error, pending/active/failed, unauthorized |
| `SCR-004` | Onboarding wizard | F-003 | Deferred / not available |
| `SCR-005` | Models and providers | F-004 | Loading, empty, create validation error, secret reference invalid, unknown provider health |
| `SCR-006` | Routes and policies | F-005, F-006, F-009 | Draft, validating, validation error, apply pending, observed, rejected, status unavailable |
| `SCR-007` | MCP governance | F-007 | Deferred / not available |
| `SCR-008` | Approvals | F-008 | Deferred / not available |
| `SCR-009` | Traces and usage | F-010 | Loading, data, no matches, partial fields, stale, telemetry unavailable |
| `SCR-010` | Budgets and cost | F-011 | Deferred / not available |
| `SCR-011` | Audit events | F-012 | Loading, events, empty, unavailable, export not supported |
| `SCR-012` | Runtime status | F-009, F-013 | Unknown, pending, observed, rejected, unavailable; no reconcile action |

## Traceability boundary

This matrix is a design map, not a test report. Application tests, builds,
gateway deployments, and live service calls have not been run for this handoff.
