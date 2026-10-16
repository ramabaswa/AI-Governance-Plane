"""Database configuration requires an explicit database URL."""

import pytest

from features.database import _database_url


def test_database_requires_explicit_url_in_development_and_test(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for environment in ("development", "test"):
        monkeypatch.setenv("ENVIRONMENT", environment)
        with pytest.raises(RuntimeError, match="DATABASE_URL must be configured"):
            _database_url()


@pytest.mark.parametrize("environment", ("", "production", "staging", "prod"))
def test_database_requires_explicit_url_outside_development_and_test(
    monkeypatch,
    environment,
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", environment)
    with pytest.raises(RuntimeError, match="DATABASE_URL must be configured"):
        _database_url()
