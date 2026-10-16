# Route Policy Revision and Rollback

**Status:** Source API and tests are present; migration, Kubernetes writes, and
live controller behavior have not been verified. This is not a production
recovery guarantee.

## Review revisions

1. Authenticate to the Control API and resolve an authorized tenant context.
2. Read `GET /api/v1/policies/routes/{route_id}/revisions`.
3. Confirm the tenant-owned route, revision number, checksum, creation actor,
   and state before choosing a source revision.

Snapshots contain declarative route fields and omit secret values. The API
recomputes and verifies the snapshot checksum before restoring it.

## Submit a rollback

Call `POST /api/v1/policies/routes/{route_id}/rollback` with:

```json
{
  "source_revision": 3
}
```

The operation restores that checksummed snapshot as desired route intent and
submits it through the same Kubernetes apply path used by normal route changes.
The API response is not proof of controller acceptance or runtime recovery.
Refresh route/controller status separately and preserve the response
correlation ID and audit evidence.

## Limitations and incident handling

- Rollback is an explicit write, not automatic remediation or a guaranteed
  recovery mechanism.
- Live Kubernetes/CRD compatibility and controller behavior have not been
  tested for this source handoff.
- Revisions are not an alternative writer/source of truth; Kubernetes remains
  the desired-state source for gateway resources.
- If apply or status observation fails, follow the deployment operator's
  approved change-management process. Do not modify managed resources through
  a second uncoordinated writer.
- Database/Kubernetes recovery requires a separately tested backup/restore
  procedure.

Deployment rollback depends on the cluster's release and rollout strategy.
The repository does not establish that a previous image is available or that
deployment rollback has been tested. Verify `/readyz` and application behavior
after any operator-led recovery.
