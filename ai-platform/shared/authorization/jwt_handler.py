"""JWT generation, signing, and verification with tenant scoping."""

import os
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
import jwt
from shared.authorization.roles import Role
from shared.errors.exceptions import UnauthorizedError, ForbiddenError

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = int(os.getenv("JWT_EXPIRATION_SECONDS", "3600"))
DEVELOPMENT_ISSUER = "urn:ai-governance-plane:development"
_OIDC_ALLOWED_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}


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
        "iss": DEVELOPMENT_ISSUER,
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
    """Verify a token against the configured provider selected by its issuer."""
    try:
        unverified_claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except jwt.PyJWTError as error:
        raise UnauthorizedError("Invalid OIDC access token") from error
    issuer = unverified_claims.get("iss")
    if not isinstance(issuer, str) or not issuer:
        raise UnauthorizedError("OIDC access token is missing a valid issuer")
    provider = _oidc_provider_configurations().get(issuer)
    if provider is None:
        raise UnauthorizedError("OIDC issuer is not configured")

    try:
        jwks_client = jwt.PyJWKClient(
            provider["jwks_url"],
            cache_jwk_set=True,
            timeout=provider["timeout_seconds"],
        )
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=provider["algorithms"],
            audience=provider["audience"],
            issuer=issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as error:
        raise UnauthorizedError("OIDC access token verification failed") from error
    except (OSError, ValueError) as error:
        raise UnauthorizedError("OIDC signing keys are unavailable") from error
    return claims


def _oidc_provider_configurations() -> dict[str, dict[str, Any]]:
    raw_providers = os.getenv("OIDC_PROVIDERS_JSON")
    if raw_providers:
        try:
            providers = json.loads(raw_providers)
        except json.JSONDecodeError as error:
            raise UnauthorizedError("OIDC_PROVIDERS_JSON is invalid JSON") from error
        if not isinstance(providers, dict) or not providers:
            raise UnauthorizedError("OIDC_PROVIDERS_JSON must be a non-empty issuer-keyed object")
    else:
        issuer = os.getenv("OIDC_ISSUER")
        audience = os.getenv("OIDC_AUDIENCE")
        jwks_url = os.getenv("OIDC_JWKS_URL")
        if not issuer or not audience or not jwks_url:
            raise UnauthorizedError(
                "Configure OIDC_PROVIDERS_JSON or OIDC_ISSUER, OIDC_AUDIENCE, and OIDC_JWKS_URL"
            )
        providers = {
            issuer: {
                "audience": audience,
                "jwks_url": jwks_url,
                "algorithms": [os.getenv("OIDC_SIGNING_ALGORITHM", "RS256")],
                "timeout_seconds": os.getenv("OIDC_JWKS_TIMEOUT_SECONDS", "5"),
            },
        }

    validated: dict[str, dict[str, Any]] = {}
    for issuer, provider in providers.items():
        if not isinstance(issuer, str) or not issuer or not isinstance(provider, dict):
            raise UnauthorizedError("OIDC provider entries must map issuer URLs to provider settings")
        issuer_url = urlsplit(issuer)
        audience = provider.get("audience")
        jwks_url = provider.get("jwks_url")
        algorithms = provider.get("algorithms")
        timeout_seconds = provider.get(
            "timeout_seconds",
            os.getenv("OIDC_JWKS_TIMEOUT_SECONDS", "5"),
        )
        if not isinstance(audience, str) or not audience or not isinstance(jwks_url, str) or not jwks_url:
            raise UnauthorizedError("OIDC provider configuration requires audience and jwks_url")
        jwks_endpoint = urlsplit(jwks_url)
        if (
            issuer_url.scheme != "https"
            or not issuer_url.hostname
            or jwks_endpoint.scheme != "https"
            or not jwks_endpoint.hostname
        ):
            raise UnauthorizedError("OIDC issuer and JWKS endpoints must use HTTPS")
        if not isinstance(algorithms, list) or not algorithms or any(
            not isinstance(algorithm, str) or algorithm not in _OIDC_ALLOWED_ALGORITHMS
            for algorithm in algorithms
        ):
            raise UnauthorizedError("OIDC provider algorithms must be approved asymmetric algorithms")
        if isinstance(timeout_seconds, bool):
            raise UnauthorizedError("OIDC JWKS timeout must be a number between 1 and 30 seconds")
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError) as error:
            raise UnauthorizedError("OIDC JWKS timeout must be a number between 1 and 30 seconds") from error
        if not 1 <= timeout <= 30:
            raise UnauthorizedError("OIDC JWKS timeout must be a number between 1 and 30 seconds")
        validated[issuer] = {
            "audience": audience,
            "jwks_url": jwks_url,
            "algorithms": algorithms,
            "timeout_seconds": timeout,
        }
    return validated


def is_development_login_enabled() -> bool:
    """
    Check if development login is permitted.
    STRICT RULE: Only enabled if ENVIRONMENT == 'development'.
    Omitted, empty, or any other value (e.g. 'production', 'staging') returns False.
    """
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    return env == "development"
