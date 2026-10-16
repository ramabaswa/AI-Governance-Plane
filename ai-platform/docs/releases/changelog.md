# Changelog

All notable changes to the AI Governance Plane platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Initial A–F control-plane source slice: OIDC verification and persisted
  tenant-membership authorization; SQLAlchemy persistence and an Alembic
  schema; tenant-scoped application/model/route APIs; hashed application-key
  catalog provisioning; Kubernetes-based gateway resource translation and
  status reads; audit evidence; and OTel/Tempo/Prometheus integration points.
- Production activation now consumes a matching approved request and issues
  its credential only after catalog provisioning; database and development
  token configuration remain environment-specific.
- Tenant-scoped approval/onboarding workflows, allowlisted MCP discovery with
  non-enforcing policy intent, advisory budgets, checksummed route revisions
  and rollback, and read-only operations observations.
- Console workflows for applications, onboarding, approvals, MCP, budgets,
  policy revisions, and operations, plus focused source tests for governance
  capabilities.
- Local Compose and Kubernetes configuration for the API, database, console,
  telemetry components, and scoped Kubernetes writer role.

### Unverified and unavailable behavior
- This is not a verified release. Tests, builds, migrations, container startup,
  browser behavior, Kubernetes/CRD compatibility, and live integrations have
  not been executed for this handoff.
- MCP policies are not gateway-enforced; FinOps hard caps and automated drift
  remediation are unavailable. Generic approval request types are not generic
  mutation executors.
- Local Compose does not include agentgateway; no end-to-end inference request
  or gateway enforcement claim is made.
