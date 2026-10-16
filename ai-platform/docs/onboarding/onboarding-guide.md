# Self-Service Onboarding

**Status:** API source is implemented; application, database, Kubernetes, and
end-to-end behavior have not been executed or validated.

## Request and review

1. An authenticated tenant member with `onboarding:create` submits
   `POST /api/v1/onboarding/requests`.
2. The tenant's authorized reviewers with `onboarding:review` can list and
   approve or deny requests through `POST
   /api/v1/onboarding/requests/{request_id}/review`.
3. Requesters cannot review their own requests. A reviewer cannot complete a
   request unless they are also the original requester.
4. After approval, only the original requester can call
   `POST /api/v1/onboarding/requests/{request_id}/complete`.

Completion creates the registered application. Eligible development and
staging requests return a generated credential once; copy it from the response.
Production requests create a draft without a credential and use the separate
production activation approval flow. If completion was committed but the
response was lost, the raw credential cannot be recovered or reissued from the
request; revoke the existing key and follow the application key lifecycle.

## Boundaries

- Tenant ID is resolved from OIDC identity and stored membership, not from the
  submitted request body.
- Requested model names are validated against active models in that tenant.
- Provider secret plaintext is never requested; supply only the approved
  Kubernetes Secret reference through model registration.
- Onboarding creates application metadata/key catalog intent. It does not
  prove that agentgateway accepted the key or that an inference request works.

See [the user guide](../users/user-guide.md) and [test
traceability](../features/test-traceability.md).
