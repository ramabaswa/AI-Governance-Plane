"""Database engine and request-scoped SQLAlchemy sessions."""

import os
import time
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from features.persistence import Base


def _database_url() -> str:
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url

    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    if environment in {"development", "test"}:
        return "sqlite:///./ai-governance.db"
    raise RuntimeError("DATABASE_URL must be configured outside development and test environments")


def create_database_engine(database_url: str | None = None) -> Engine:
    url = database_url or _database_url()
    options: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


engine = create_database_engine()
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    with SessionFactory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def initialize_development_schema() -> None:
    if os.getenv("ENVIRONMENT", "").strip().lower() not in {"development", "test"}:
        raise RuntimeError("Automatic schema creation is restricted to development and test environments")
    Base.metadata.create_all(bind=engine)


def seed_development_data() -> None:
    """Create local-only sample tenant, model catalog, and memberships."""
    if os.getenv("ENVIRONMENT", "").strip().lower() not in {"development", "test"}:
        raise RuntimeError("Development data seeding is restricted to development and test environments")

    from features.persistence import ModelBackendRecord, TenantMembershipRecord, TenantRecord
    from shared.authorization.jwt_handler import DEVELOPMENT_ISSUER
    from shared.authorization.roles import Role

    now = int(time.time())
    with SessionFactory.begin() as session:
        tenants = {
            "tenant-acme": ("Acme Corp", "acme-corp"),
            "platform": ("Platform", "platform"),
        }
        for tenant_id, (name, slug) in tenants.items():
            if session.get(TenantRecord, tenant_id) is None:
                session.add(TenantRecord(
                    id=tenant_id,
                    name=name,
                    slug=slug,
                    created_at=now,
                    updated_at=now,
                    is_active=True,
                ))
        session.flush()

        memberships = {
            ("admin@acme.internal", "tenant-acme"): [Role.TENANT_ADMIN.value],
            ("dev@acme.internal", "tenant-acme"): [Role.DEVELOPER.value],
            ("auditor@acme.internal", "tenant-acme"): [Role.AUDITOR.value],
            ("root@platform.internal", "platform"): [Role.PLATFORM_ADMIN.value],
        }
        for (subject, tenant_id), roles in memberships.items():
            existing = session.scalar(
                select(TenantMembershipRecord.id).where(
                    TenantMembershipRecord.issuer == DEVELOPMENT_ISSUER,
                    TenantMembershipRecord.subject == subject,
                    TenantMembershipRecord.tenant_id == tenant_id,
                )
            )
            if existing is None:
                session.add(TenantMembershipRecord(
                    issuer=DEVELOPMENT_ISSUER,
                    subject=subject,
                    tenant_id=tenant_id,
                    roles=roles,
                    created_at=now,
                ))

        sample_models = [
            ("model-claude-35", "claude-3-5-sonnet", "anthropic", "claude-3-5-sonnet-20241022", "anthropic-secret/api-key", 0.003, 0.015),
            ("model-gpt4o", "gpt-4o", "openai", "gpt-4o", "openai-secret/api-key", 0.005, 0.015),
        ]
        for model_id, name, provider, model_name, secret_ref, input_cost, output_cost in sample_models:
            if session.get(ModelBackendRecord, model_id) is None:
                session.add(ModelBackendRecord(
                    id=model_id,
                    tenant_id="tenant-acme",
                    name=name,
                    provider=provider,
                    model_name=model_name,
                    secret_ref=secret_ref,
                    cost_per_1k_input_tokens=input_cost,
                    cost_per_1k_output_tokens=output_cost,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ))
