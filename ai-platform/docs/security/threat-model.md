# Security Boundaries and Known Limitations

**Status:** Static description of the A–F source implementation, not a security
review or certification. Tests and deployment controls have not been executed
or independently validated for this handoff.

## Trust boundaries

```text
User
  └─ OIDC bearer token ─> Control API
       ├─ persisted tenant membership / role authorization ─> SQL database
       ├─ management writes ─> Kubernetes API ─> agentgateway controller
       └─ tenant-authorized reads ─> Tempo / Prometheus

Application / agent
  └─ workload API key ─> agentgateway ─> configured provider/backend
```

The Control API does not proxy inference. API credentials are stored in the
database as SHA-256 verifier hashes and placed in the gateway key catalog as
`sha256:` key hashes; raw issued credentials are returned once. Production
application records remain drafts and receive no key while approval workflows
are deferred. A Kubernetes API write is not proof that the controller or
gateway accepted the resource.

## Threats and implemented controls

| Threat | Source-level control | Limit / required validation |
|---|---|---|
| Spoofed user identity or tenant selection | OIDC signature, issuer, audience, and required-claim verification; tenant roles are loaded from persisted memberships rather than token role claims or a caller-selected tenant header. Local login is development-only. | Real provider/JWKS integration, key rotation, deployment configuration, and authorization tests remain unverified. |
| Cross-tenant data disclosure | Tenant-scoped database queries and authorization dependencies are used on active management routes. | Verify every route and role combination against a live database; no independent security test was run. |
| Credential disclosure or replay | Raw application keys are one-time responses; persistent/catalog form is a SHA-256 hash. Local JWT signing requires an explicit `JWT_SECRET`. | Secure transport, key rotation, credential expiry, gateway key-cache behavior, and revocation propagation are not verified. |
| Unauthorized production activation | Production applications are drafts, do not receive keys, and cannot transition to active while approval is unavailable. | No approval workflow exists. Lifecycle transition coverage and authorization must be tested; approval is not implied by a draft state. |
| Management event tampering | Audit events include a hash chain and audit reads are recorded. | Hash chaining is not immutable storage or a compliance guarantee; database administrators may alter data, and retention/export controls are not verified. |
| Malicious guardrail expression | Regex validation rejects selected unsafe patterns before translation. | The validator is not a complete ReDoS proof; runtime policy behavior and resource limits are unverified. |
| Misleading operational evidence | Route reconciliation reads Kubernetes resource status; observability returns explicit unavailable states rather than fabricating gateway usage. | CRD/controller condition semantics and tenant-scoped gateway telemetry have not been exercised. |
| Resource exhaustion or abuse | No hard budget or cost enforcement is claimed. | Request rate limiting, inference quotas, and denial-of-service protections are not implemented by this slice. |

## Deployment requirements

- Use a production OIDC issuer, audience, and JWKS endpoint over trusted
  transport.
- Set `DATABASE_URL` to a supported durable database. SQLite is selected by
  default only in development/test.
- Keep provider credentials in the referenced Kubernetes Secret system; the
  platform persists references, not provider secret plaintext.
- Review the namespace-scoped writer Role and RoleBinding against the
  deployment namespace and installed CRDs.
- Restrict CORS origins and network access for the environment. Do not expose
  development login outside development.
- Configure TLS, database backup/restore, audit retention, telemetry access,
  and Kubernetes control-plane protections operationally; these are not
  established by application source alone.

## Verification gaps

No security review, penetration test, dependency scan, secret scan, production
configuration validation, live OIDC test, live Kubernetes authorization
check, or gateway credential-revocation test was performed. MCP, approvals,
budgets, autonomous remediation, and tool-level policies are deferred and
must not be represented as security controls in this release slice.
