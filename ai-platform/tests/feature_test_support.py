"""Reusable isolated database setup for package-local feature unit tests."""

import time
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from features.persistence import Base, GatewayRouteRecord, ModelBackendRecord, TenantRecord


@contextmanager
def feature_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = int(time.time())
    try:
        with Session(engine, expire_on_commit=False) as session:
            session.add_all([
                TenantRecord(
                    id=tenant_id,
                    name=tenant_id,
                    slug=tenant_id,
                    created_at=now,
                    updated_at=now,
                    is_active=True,
                )
                for tenant_id in ("tenant-acme", "tenant-globex", "platform")
            ])
            session.add(ModelBackendRecord(
                id="model-test",
                tenant_id="tenant-acme",
                name="test-model",
                provider="anthropic",
                model_name="claude-test",
                secret_ref="provider-secret/api-key",
                cost_per_1k_input_tokens=0,
                cost_per_1k_output_tokens=0,
                is_active=True,
                created_at=now,
                updated_at=now,
            ))
            session.add(GatewayRouteRecord(
                id="route-test",
                tenant_id="tenant-acme",
                name="test-route",
                path_prefix="/v1/test",
                backend_model_id="model-test",
                failover_model_ids=[],
                traffic_weights={"model-test": 100},
                dlp_rules=[],
                rate_limit_rpm=None,
                revision_id=1,
                lifecycle_state="draft",
                created_at=now,
                updated_at=now,
            ))
            session.flush()
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
