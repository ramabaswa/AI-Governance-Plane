# Backup and Restore Considerations

**Status:** No backup schedule, retention policy, or restore exercise has been
configured or verified for this implementation.

## State that requires protection

- PostgreSQL holds tenant memberships, application/model/route metadata,
  virtual-key verifier hashes, and audit events.
- Kubernetes Gateway API and agentgateway resources are the active desired
  gateway configuration and must be included in the operator's cluster backup
  strategy.
- Plaintext application keys are not recoverable from verifier hashes. A
  restore must not reissue the original raw credential as though it were
  available.
- Provider credentials remain in the external Kubernetes Secret store.
  Database backups must not be treated as backups of provider secret material.

## Before production use

Operators must define and test:

1. PostgreSQL backup frequency, encryption, access control, retention, and
   point-in-time recovery.
2. Kubernetes resource and Secret backup policies with appropriate protection
   for credential material.
3. Audit event retention and integrity verification expectations.
4. Recovery ordering for the database, Kubernetes desired resources, Control
   API, telemetry services, and gateway controller.
5. A recovery exercise that verifies tenant membership, credential state,
   route status, and audit-chain continuity without claiming restored gateway
   runtime state prematurely.

Do not use the old example schedules, S3 paths, retention periods, or worker
reconciliation commands as configured procedures; none is established by this
repository.
