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
- Production application records remain drafts without credentials while the
  approval workflow is deferred; a database URL and explicit development JWT
  secret are required in their respective non-test environments.
- A limited console for the implemented API surfaces and focused tests for
  identity, API behavior, translation, reconciliation, security boundaries,
  and observability.
- Local Compose and Kubernetes configuration for the API, database, console,
  telemetry components, and scoped Kubernetes writer role.

### Deferred and unverified
- This is not a verified release. Tests, builds, migrations, container startup,
  browser behavior, Kubernetes/CRD compatibility, and live integrations have
  not been executed for this handoff.
- MCP governance, onboarding, approvals, budgets/cost metering, and automated
  drift remediation are not part of this implementation slice.
- Local Compose does not include agentgateway; no end-to-end inference request
  or gateway enforcement claim is made.
