"""Identity Provider adapter supporting local development and enterprise OIDC."""

import os
from typing import Dict, Any, Optional
from shared.authorization.roles import Role
from shared.authorization.jwt_handler import create_access_token, is_development_login_enabled
from shared.errors.exceptions import UnauthorizedError, ForbiddenError

# Built-in seed accounts for local development mode
DEV_ACCOUNTS = {
    "admin@acme.internal": {
        "password": "devpassword123!",
        "tenant_id": "tenant-acme",
        "roles": [Role.TENANT_ADMIN],
    },
    "dev@acme.internal": {
        "password": "devpassword123!",
        "tenant_id": "tenant-acme",
        "roles": [Role.DEVELOPER],
    },
    "auditor@acme.internal": {
        "password": "devpassword123!",
        "tenant_id": "tenant-acme",
        "roles": [Role.AUDITOR],
    },
    "root@platform.internal": {
        "password": "devpassword123!",
        "tenant_id": "platform",
        "roles": [Role.PLATFORM_ADMIN],
    },
}


class IdentityProvider:
    """Manages user authentication and token exchange."""

    @staticmethod
    def authenticate_development_user(username: str, password: str, tenant_id: Optional[str] = None) -> str:
        """
        Authenticate local development user.
        CRITICAL RULE:
        1. Local login is DISABLED outside development (test_local_login_is_disabled_outside_development).
        2. Omitted environment DOES NOT enable development login (test_omitted_environment_does_not_enable_development_login).
        """
        if not is_development_login_enabled():
            raise UnauthorizedError(
                "Local development login is disabled in this environment. Please authenticate via enterprise OIDC provider."
            )

        account = DEV_ACCOUNTS.get(username)
        if not account or account["password"] != password:
            raise UnauthorizedError("Invalid email or password")

        # Use requested tenant if platform admin, else user's assigned tenant
        effective_tenant = account["tenant_id"]
        if tenant_id and Role.PLATFORM_ADMIN in account["roles"]:
            effective_tenant = tenant_id

        return create_access_token(
            subject=username,
            tenant_id=effective_tenant,
            roles=account["roles"],
        )
