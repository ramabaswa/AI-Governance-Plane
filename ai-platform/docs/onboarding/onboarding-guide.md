# Onboarding Scope

**Status:** Self-service onboarding (F-003) and MCP onboarding are deferred;
their routers and workflows are not part of the active API.

## Application registration

Application registration is available directly through the tenant-scoped
application API and console, not through a four-step onboarding wizard.

- Tenant membership and permissions determine access; a client-selected
  tenant is not authority.
- Development and staging registrations may receive a one-time generated
  credential. The raw credential is not returned on subsequent reads.
- Production applications are stored as drafts without credentials. They
  cannot be activated while the approval workflow is unavailable.
- Model credentials are represented by Kubernetes Secret references; the
  Control API does not accept provider secret plaintext.

Credential catalog configuration and controller/runtime observation are
separate states. A catalog write does not establish that agentgateway accepted
or used a key.

## MCP onboarding

MCP server registration, discovery, policy management, and tool invocation are
not available in the active A–F implementation. Do not use this guide as
instructions to configure a live MCP integration. Any future MCP workflow
requires separate scope approval and end-to-end compatibility validation.

For supported setup steps, see the [project README](../../README.md).
