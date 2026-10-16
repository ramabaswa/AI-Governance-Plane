import pytest

from integrations.identity.provider import IdentityProvider
from shared.authorization.jwt_handler import decode_access_token
from shared.errors.exceptions import UnauthorizedError


def test_development_authentication_issues_token_for_seeded_account(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET", "unit-test-development-secret")

    token = IdentityProvider.authenticate_development_user(
        "dev@acme.internal",
        "devpassword123!",
    )
    claims = decode_access_token(token)

    assert claims["sub"] == "dev@acme.internal"
    assert claims["tenant_id"] == "tenant-acme"


def test_invalid_development_password_is_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET", "unit-test-development-secret")

    with pytest.raises(UnauthorizedError, match="Invalid email or password"):
        IdentityProvider.authenticate_development_user(
            "dev@acme.internal",
            "wrong-password",
        )
