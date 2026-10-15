# Implementation and Verification Plan

**Status:** Gates 0–2 approved; the approved A–F implementation and its focused
tests have been added. Gate 3 execution has not been authorized.

## Guardrails

1. Preserve the existing repository and user changes; do not clean, reset, or
   remove unrelated files.
2. Keep Python/FastAPI, the current console, PostgreSQL, generic OIDC, and the
   selected OTel/Tempo/Prometheus stack.
3. Keep inference traffic on agentgateway; the Control API is not an inference
   proxy.
4. Distinguish desired state, Kubernetes write acknowledgement, controller
   status, and runtime request evidence.
5. Do not claim production identity, gateway enforcement, real usage metrics,
   migrations, deployment readiness, or passing tests without execution
   evidence.
6. MCP, onboarding, approvals, FinOps/budgets, and automated drift remediation
   are outside the approved A–F slice.

## Gate status

### Gates 0–2 — Complete

The existing workspace was assessed, upstream/source references and scope
were reviewed, and wireframes/interactions were approved. The approved
implementation choices are PostgreSQL, generic OIDC, OTel Collector with
Tempo/Prometheus, snake_case Python feature packages, and the A–F control-plane
slice.

### Gate 3 — Implementation present; execution pending

The A–F source changes, focused tests, Kubernetes/deployment configuration,
console updates, and related documentation are present. Tests, builds,
migrations, containers, deployments, browser checks, and live integrations
remain unexecuted per the user's instruction.

The next step is to obtain authorization before running focused checks.
Verification should report exact commands and results, and should not be
expanded into production deployment or release actions without separate
approval.

### Gate 4 — Hardening and system validation (not started)

After Gate 3 evidence is reviewed and approved:

1. Execute applicable API, authorization, persistence, translator,
   reconciliation, observability, and UI tests.
2. Validate PostgreSQL migrations and production configuration.
3. Test the pinned agentgateway resources and request path in an isolated
   Kubernetes environment, if available and authorized.
4. Review security, tenant isolation, credential lifecycle, failure handling,
   recovery, and unresolved compatibility gaps.

### Gate 5 — CI/CD and release (not started)

Requires separate approval after Gate 4 evidence. Review existing workflows,
least privilege, dependency/secret scanning, reproducible artifacts,
migrations, release, and rollback. Do not publish or deploy without explicit
authorization.

## Completion boundary

Source implementation and documentation do not establish a passing test
baseline or an operational service. Gate 3 remains pending until execution is
authorized and its results are reported; later hardening/release work remains
gated on review and approval.
