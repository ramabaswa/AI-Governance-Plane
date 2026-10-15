"""Tests for OIDC JWT verification and database-authoritative roles."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from shared.authorization.jwt_handler import verify_oidc_token
from shared.errors.exceptions import UnauthorizedError


def _oidc_token(private_key, audience="governance-api"):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "oidc-subject-123",
            "iss": "https://identity.example.test/",
            "aud": audience,
            "iat": now,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def _patch_jwks(monkeypatch, public_key):
    monkeypatch.setattr(
        jwt,
        "PyJWKClient",
        lambda *_args, **_kwargs: SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=public_key)
        ),
    )


def test_oidc_verification_checks_signature_issuer_audience_and_required_claims(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _patch_jwks(monkeypatch, private_key.public_key())
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/")
    monkeypatch.setenv("OIDC_AUDIENCE", "governance-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://identity.example.test/.well-known/jwks.json")

    claims = verify_oidc_token(_oidc_token(private_key))
    assert claims["sub"] == "oidc-subject-123"


def test_oidc_verification_rejects_wrong_audience(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _patch_jwks(monkeypatch, private_key.public_key())
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/")
    monkeypatch.setenv("OIDC_AUDIENCE", "governance-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://identity.example.test/.well-known/jwks.json")

    with pytest.raises(UnauthorizedError):
        verify_oidc_token(_oidc_token(private_key, audience="other-api"))


def test_oidc_verification_rejects_invalid_signature(monkeypatch):
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    unrelated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _patch_jwks(monkeypatch, unrelated_key.public_key())
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/")
    monkeypatch.setenv("OIDC_AUDIENCE", "governance-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://identity.example.test/.well-known/jwks.json")

    with pytest.raises(UnauthorizedError):
        verify_oidc_token(_oidc_token(signing_key))


def test_local_token_signing_requires_explicit_secret(monkeypatch):
    from shared.authorization.jwt_handler import create_access_token

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET must be configured"):
        create_access_token("user-1", "tenant-1", [])


def test_local_token_signing_is_disabled_outside_development_and_tests(monkeypatch):
    from shared.authorization.jwt_handler import create_access_token

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "configured-but-not-usable-for-local-login")
    with pytest.raises(UnauthorizedError, match="Local token signing is available only"):
        create_access_token("user-1", "tenant-1", [])
