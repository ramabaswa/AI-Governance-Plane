"""JWT generation, signing, and verification with tenant scoping."""

import os
import time
from typing import Any, Dict, List, Optional
import jwt
from shared.authorization.roles import Role
from shared.errors.exceptions import UnauthorizedError, ForbiddenError

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = int(os.getenv("JWT_EXPIRATION_SECONDS", "3600"))


def _local_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET must be configured for local token signing and verification")
    return secret


def create_access_token(
    subject: str,
    tenant_id: str,
    roles: List[Role],
    expires_delta: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT token containing tenant_id and assigned roles."""
    if os.getenv("ENVIRONMENT", "").strip().lower() not in {"development", "test"}:
        raise UnauthorizedError("Local token signing is available only in development or tests")
    now = int(time.time())
    exp = now + (expires_delta if expires_delta is not None else JWT_EXPIRATION_SECONDS)

    payload: Dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": [r.value if isinstance(r, Role) else str(r) for r in roles],
        "iat": now,
        "exp": exp,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, _local_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode a local development token. Never use for external identity tokens."""
    if os.getenv("ENVIRONMENT", "").strip().lower() not in {"development", "test"}:
        raise UnauthorizedError("Local token verification is available only in development or tests")
    try:
        payload = jwt.decode(token, _local_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError(f"Invalid authentication token: {str(e)}")


def verify_oidc_token(token: str) -> Dict[str, Any]:
    """Verify a bearer token against the configured OIDC issuer and JWKS endpoint."""
    issuer = os.getenv("OIDC_ISSUER")
    audience = os.getenv("OIDC_AUDIENCE")
    jwks_url = os.getenv("OIDC_JWKS_URL")
    algorithm = os.getenv("OIDC_SIGNING_ALGORITHM", "RS256")
    allowed_algorithms = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}

    if not issuer or not audience or not jwks_url:
        raise UnauthorizedError("OIDC_ISSUER, OIDC_AUDIENCE, and OIDC_JWKS_URL must be configured")
    if algorithm not in allowed_algorithms:
        raise UnauthorizedError("OIDC_SIGNING_ALGORITHM must be an approved asymmetric algorithm")

    try:
        jwks_client = jwt.PyJWKClient(jwks_url, cache_jwk_set=True)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as error:
        raise UnauthorizedError(f"Invalid OIDC access token: {error}") from error
    except (OSError, ValueError) as error:
        raise UnauthorizedError("Unable to verify OIDC access token") from error
    return claims


def is_development_login_enabled() -> bool:
    """
    Check if development login is permitted.
    STRICT RULE: Only enabled if ENVIRONMENT == 'development'.
    Omitted, empty, or any other value (e.g. 'production', 'staging') returns False.
    """
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    return env == "development"
