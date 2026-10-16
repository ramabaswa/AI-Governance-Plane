"""Role definitions and permission checks for AI Governance Control Plane."""

from enum import Enum
from typing import Set


class Role(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    TENANT_ADMIN = "tenant_admin"
    DEVELOPER = "developer"
    AUDITOR = "auditor"
    VIEWER = "viewer"


ROLE_HIERARCHY = {
    Role.PLATFORM_ADMIN: {
        "tenant:create", "tenant:read", "tenant:update", "tenant:delete",
        "app:create", "app:read", "app:update", "app:delete", "app:lifecycle",
        "route:create", "route:read", "route:update", "route:delete", "route:apply",
        "model:create", "model:read", "model:update", "model:delete",
        "mcp:create", "mcp:read", "mcp:update", "mcp:delete",
        "approval:read", "approval:create", "approval:decide",
        "onboarding:create",
        "onboarding:review",
        "finops:read", "finops:update",
        "mcp:discover",
        "audit:read", "audit:export",
        "operations:read", "operations:reconcile",
    },
    Role.TENANT_ADMIN: {
        "tenant:read", "tenant:update",
        "app:create", "app:read", "app:update", "app:delete", "app:lifecycle",
        "route:create", "route:read", "route:update", "route:delete", "route:apply",
        "model:create", "model:read", "model:update",
        "mcp:create", "mcp:read", "mcp:update",
        "approval:read", "approval:create", "approval:decide",
        "onboarding:create",
        "onboarding:review",
        "finops:read", "finops:update",
        "mcp:discover",
        "audit:read", "audit:export",
        "operations:read",
    },
    Role.DEVELOPER: {
        "tenant:read",
        "app:create", "app:read", "app:update",
        "route:read",
        "model:read",
        "mcp:read",
        "approval:read", "approval:create",
        "onboarding:create",
        "finops:read",
        "audit:read",
    },
    Role.AUDITOR: {
        "tenant:read",
        "app:read",
        "route:read",
        "model:read",
        "mcp:read",
        "approval:read",
        "audit:read", "audit:export",
        "operations:read",
    },
    Role.VIEWER: {
        "tenant:read",
        "app:read",
        "route:read",
        "model:read",
        "mcp:read",
        "finops:read",
        "operations:read",
        "approval:read",
    },
}


def has_permission(role: Role, permission: str) -> bool:
    perms = ROLE_HIERARCHY.get(role, set())
    return permission in perms
