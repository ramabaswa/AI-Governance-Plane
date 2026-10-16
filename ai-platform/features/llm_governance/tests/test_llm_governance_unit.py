import pytest

from features.llm_governance import service
from tests.feature_test_support import feature_database
from shared.contracts.model import ModelBackendCreate, ProviderType
from shared.errors.exceptions import ResourceConflictError, ValidationError


def _model(**overrides):
    values = {
        "name": "new-model",
        "provider": ProviderType.ANTHROPIC,
        "model_name": "claude-test",
        "secret_ref": "provider-secret/api-key",
    }
    values.update(overrides)
    return ModelBackendCreate(**values)


def test_model_catalog_is_tenant_scoped_and_rejects_duplicate_names():
    with feature_database() as session:
        created = service.create_model(
            session,
            tenant_id="tenant-acme",
            actor="admin",
            request=_model(),
        )
        assert created.tenant_id == "tenant-acme"
        assert [model.id for model in service.list_models(session, "tenant-acme")] == [created.id]
        assert service.list_models(session, "tenant-globex") == []
        with pytest.raises(ResourceConflictError):
            service.create_model(
                session,
                tenant_id="tenant-acme",
                actor="admin",
                request=_model(),
            )
        with pytest.raises(ValidationError, match="not supported"):
            service.create_model(
                session,
                tenant_id="tenant-acme",
                actor="admin",
                request=_model(base_url="https://provider.example.test"),
            )
