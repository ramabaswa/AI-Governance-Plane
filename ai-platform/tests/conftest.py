"""Isolated relational fixtures for API tests."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.control_api.main import app
from apps.control_api.dependencies import get_agentgateway_kubernetes_client
from features.database import get_db_session
from features.persistence import Base, ModelBackendRecord, TenantMembershipRecord, TenantRecord
from shared.authorization.jwt_handler import DEVELOPMENT_ISSUER
from shared.authorization.roles import Role


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-for-local-token-tests")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'control-plane-test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_session():
        with test_sessions() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    class FakeKubernetesClient:
        def __init__(self):
            self.resources = []

        def apply(self, resources):
            self.resources.extend(resources)

    app.dependency_overrides[get_db_session] = override_session
    fake_kubernetes_client = FakeKubernetesClient()
    app.dependency_overrides[get_agentgateway_kubernetes_client] = lambda: fake_kubernetes_client
    app.state.test_kubernetes_client = fake_kubernetes_client
    now = int(time.time())
    with test_sessions.begin() as session:
        for tenant_id, name, slug in (
            ("tenant-acme", "Acme Corp", "acme-corp"),
            ("tenant-globex", "Globex", "globex"),
            ("platform", "Platform", "platform"),
        ):
            session.add(TenantRecord(
                id=tenant_id,
                name=name,
                slug=slug,
                created_at=now,
                updated_at=now,
                is_active=True,
            ))
        for subject, tenant_id, roles in (
            ("admin@acme.internal", "tenant-acme", [Role.TENANT_ADMIN.value]),
            ("dev@acme.internal", "tenant-acme", [Role.DEVELOPER.value]),
            ("auditor@acme.internal", "tenant-acme", [Role.AUDITOR.value]),
            ("root@platform.internal", "platform", [Role.PLATFORM_ADMIN.value]),
            ("dev@globex.internal", "tenant-globex", [Role.DEVELOPER.value]),
        ):
            session.add(TenantMembershipRecord(
                issuer=DEVELOPMENT_ISSUER,
                subject=subject,
                tenant_id=tenant_id,
                roles=roles,
                created_at=now,
            ))
        session.add(ModelBackendRecord(
            id="model-claude-35",
            tenant_id="tenant-acme",
            name="claude-3-5-sonnet",
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            secret_ref="anthropic-secret/api-key",
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))

    try:
        with TestClient(app) as client:
            yield client, test_sessions
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_agentgateway_kubernetes_client, None)
        del app.state.test_kubernetes_client
        Base.metadata.drop_all(engine)
        engine.dispose()
