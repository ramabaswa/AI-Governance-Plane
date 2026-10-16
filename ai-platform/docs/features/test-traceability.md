# Test Traceability

**Status:** Coverage mapped to current source tests; no tests were executed for
this implementation handoff. Every verification result below is unverified.

| Feature | Test coverage | Test file and function | Verification |
|---|---|---|---|
| F-001 Authentication and tenant access | Local login is environment-gated; client tenant selection and token role claims cannot grant authority; platform-admin membership administration is checked. | `tests/test_control_plane.py::test_local_login_is_disabled_outside_development`; `tests/test_control_plane.py::test_client_cannot_choose_unassigned_tenant`; `tests/test_control_plane.py::test_platform_admin_can_manage_tenant_memberships`; `tests/test_control_plane.py::test_tenant_admin_cannot_manage_memberships`; `tests/test_control_plane.py::test_role_claims_do_not_grant_tenant_authority`; `tests/test_identity.py::test_oidc_verification_checks_signature_issuer_audience_and_required_claims`; `tests/test_identity.py::test_oidc_verification_rejects_wrong_audience`; `tests/test_identity.py::test_oidc_verification_rejects_invalid_signature` | Unverified — not run |
| Configuration safety | Database defaults to SQLite only in development/test; local token signing requires an explicit secret and is disabled elsewhere. | `tests/test_database.py::test_database_uses_sqlite_by_default_in_development_and_test`; `tests/test_database.py::test_database_requires_explicit_url_outside_development_and_test`; `tests/test_identity.py::test_local_token_signing_requires_explicit_secret`; `tests/test_identity.py::test_local_token_signing_is_disabled_outside_development_and_tests` | Unverified — not run |
| F-002 Application and key lifecycle | Tenant-scoped registration, one-time key return, separate approval for production activation, failed provisioning and revocation recovery. | `tests/test_control_plane.py::test_application_registration_is_tenant_scoped_and_key_is_one_time`; `tests/test_control_plane.py::test_production_application_cannot_skip_approval`; `tests/test_control_plane.py::test_production_activation_requires_approved_separate_requester`; `tests/test_control_plane.py::test_key_revocation_updates_the_desired_key_catalog`; `tests/test_control_plane.py::test_key_revocation_can_retry_failed_catalog_update`; `tests/test_control_plane.py::test_failed_key_provisioning_reports_cleanup_failure_and_can_be_retried` | Unverified — not run |
| F-004 Model/backend registry | No focused model CRUD or provider-secret integration test currently exists. | — | Not covered |
| F-005 Routes and gateway resources | Route duplicate handling, validation-only behavior, persisted status transitions, revision-tagged Kubernetes resources, lazy Kubernetes credentials, observed-status reconciliation, stale-revision pending state, controller rejection, and partial apply errors. | `tests/test_control_plane.py::test_duplicate_route_conflicts_and_validation_only_emits_candidate_resources`; `tests/test_control_plane.py::test_route_status_transitions_replace_stale_observed_state`; `tests/test_gateway_translator.py::test_translator_generates_backend_route_and_guard_policy_crds`; `tests/test_gateway_translator.py::test_yaml_output_contains_only_generated_kubernetes_resources`; `tests/integration/test_agentgateway_reconcile.py::test_kubernetes_credentials_are_loaded_only_for_resource_operations`; `tests/integration/test_agentgateway_reconcile.py::test_reconciler_reports_only_controller_observed_status`; `tests/integration/test_agentgateway_reconcile.py::test_reconciler_surfaces_controller_rejection`; `tests/integration/test_agentgateway_reconcile.py::test_reconciler_keeps_stale_route_revision_pending`; `tests/integration/test_agentgateway_reconcile.py::test_reconciler_surfaces_partial_apply_conflicts` | Unverified — not run; no live gateway test |
| F-006 Supported guardrails | Regex ReDoS pattern rejection and generated prompt-guard resource shape. | `tests/security/test_security_boundaries.py::test_redos_catastrophic_backtracking_pattern_rejected`; `tests/test_gateway_translator.py::test_translator_generates_backend_route_and_guard_policy_crds` | Unverified — not run |
| F-003 Self-service onboarding | Request submission/review, separation of duties, requester-only completion and one-time eligible credential delivery. | `tests/test_extended_features.py::test_onboarding_requires_reviewer_and_only_requester_can_complete` | Unverified — not run |
| F-007 MCP governance | Real protocol discovery through an injected HTTP transport; exact-host allowlisting; management policies explicitly not gateway-enforced. | `tests/test_extended_features.py::test_mcp_discovery_uses_real_protocol_and_enforces_host_allowlist`; `tests/test_extended_features.py::test_mcp_discovery_refuses_unallowlisted_hosts_without_network_access` | Unverified — not run |
| F-008 Approvals | Tenant-scoped durable requests, self-approval rejection, separate reviewer and one-time application to production activation. | `tests/test_control_plane.py::test_production_activation_requires_approved_separate_requester` | Unverified — not run |
| F-009 Policy lifecycle | Checksummed route revision snapshots and rollback that creates a new revision. | `tests/test_extended_features.py::test_policy_revisions_are_persisted_and_rollback_creates_a_new_revision` | Unverified — not run; no live rollback |
| F-011 FinOps | Persistent budget policy, missing spend remains unknown, hard-cap attempts rejected. | `tests/test_extended_features.py::test_finops_reports_unknown_spend_and_rejects_unavailable_hard_cap` | Unverified — not run |
| F-013 Operations | Tenant-scoped read-only status endpoint; no automatic writes. | `tests/test_extended_features.py::test_operations_drift_endpoint_is_read_only_and_tenant_scoped` | Unverified — not run |
| F-010 Observability | No fabricated usage fields; configured Prometheus metrics and explicit unavailability when metrics or sources are missing. | `tests/test_observability.py::test_tempo_trace_results_do_not_invent_usage_fields`; `tests/test_observability.py::test_prometheus_returns_observed_values_and_explicit_unconfigured_metrics`; `tests/test_observability.py::test_observability_source_absence_is_an_explicit_error` | Unverified — not run |
| F-012 Audit evidence | Audit reads are recorded and tampering with event details invalidates the hash chain. | `tests/test_control_plane.py::test_audit_read_is_chained_and_itself_audited`; `tests/test_control_plane.py::test_audit_chain_detects_mutated_event_details` | Unverified — not run |
| Security boundaries | Secret references are masked in logs. | `tests/security/test_security_boundaries.py::test_secret_reference_manager_masks_tokens_in_logs` | Unverified — not run |
| API surface | OpenAPI includes implemented governance routes and excludes an inference proxy. | `tests/test_control_plane.py::test_openapi_exposes_governance_routes_without_inference_proxy` | Unverified — not run |

## Explicit coverage gaps

- No end-to-end request has been sent through a live agentgateway to a backend.
- No test currently verifies a real OIDC provider/JWKS endpoint, production deployment configuration, or role/membership administration matrix.
- Gateway key catalog changes still lack verification against a live controller/runtime; the focused failure/retry test is unrun.
- No live Kubernetes API/CRD compatibility, Alembic migration, PostgreSQL durability, Tempo, or Prometheus integration has been exercised.
- No live MCP server, gateway MCP policy enforcement, production approval workflow under concurrency, full month-scoped Prometheus spend query, or database migration was exercised.
- FinOps hard-cap enforcement and automatic drift remediation are not implemented by design; current tests verify those limits are not represented as successful controls.

## Focused service and live integration checks

Every direct package under `features/` and `integrations/` now has a local
`tests/` directory with at least one unit test. These complement the broader
suite under `tests/features/` and `tests/integrations/`. Pytest collection
includes `tests/`, `features/`, and `integrations/` through `testpaths` in
`pyproject.toml`. Integration-boundary unit tests still use deterministic
Kubernetes API doubles; they do not require a cluster.
The pre-existing `tests/integration/test_agentgateway_reconcile.py` is also
deterministic and is not a live-cluster test.

The opt-in `tests/integration/test_live_agentgateway.py` checks the health and
readiness of a running Control API, then reads controller observations for an
existing route. It does not create or delete Kubernetes resources. A separate
real inference smoke request is gated by both `AGP_RUN_LIVE_INTEGRATION=1` and
`AGP_LIVE_ALLOW_INFERENCE_REQUEST=1`.

To run live checks from `ai-platform/`, explicitly configure:

```bash
AGP_RUN_LIVE_INTEGRATION=1 \
AGP_LIVE_CONTROL_API_URL=https://control-api.example.test \
AGP_LIVE_OIDC_TOKEN='<short-lived OIDC token>' \
AGP_LIVE_TENANT_ID='<authorized tenant>' \
AGP_LIVE_ROUTE_ID='<existing route ID>' \
pytest -m live_integration tests/integration/test_live_agentgateway.py
```

For the optional inference request, additionally provide
`AGP_LIVE_ALLOW_INFERENCE_REQUEST=1`, `AGP_LIVE_INFERENCE_URL`,
`AGP_LIVE_INFERENCE_API_KEY`, and `AGP_LIVE_INFERENCE_REQUEST_JSON`. Use a
dedicated test gateway/backend and a non-sensitive request body. These live
tests are not executed by the default suite because they are marked
`live_integration` and skip unless explicitly enabled.

Do not mark any row as passed until its test has actually run. Record the exact
command, environment, date, and outcome when test execution is authorized.
