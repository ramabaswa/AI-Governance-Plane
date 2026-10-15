# Rollback Limitations

**Status:** The active A–F API does not implement route revision history or a
rollback operation. This document is not an executable rollback runbook.

## Gateway configuration

- The routes API supports validation, resource submission, and observed-status
  reads; it does not expose a prior-revision selector or rollback endpoint.
- Do not call a `/routes/{route_id}/rollback` endpoint or assume that the
  console can restore a prior revision.
- If an applied resource must be changed urgently, use the approved
  change-management process and the existing Kubernetes resource/controller
  path. Identify the exact desired resource, preserve audit evidence, and
  verify the resulting controller status. Do not modify managed resources
  through a second uncoordinated writer.
- Recovery of Kubernetes objects or database records is an operator-led
  process and requires a tested backup/restore procedure.

## Control API deployment

Deployment rollback depends on the cluster's release and rollout strategy.
The repository does not establish that a particular previous image is
available or that rollback has been tested. Follow the deployment operator's
approved procedure and verify `/readyz` and application behavior afterward.

Revision history, automated rollback, and production promotion remain
deferred features.
