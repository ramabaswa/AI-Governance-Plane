"""Database engine and request-scoped SQLAlchemy sessions."""

import os
import time
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from features.persistence import Base


def _database_url() -> str:
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url
    raise RuntimeError("DATABASE_URL must be configured")


def create_database_engine(database_url: str | None = None) -> Engine:
    url = database_url or _database_url()
    return create_engine(url, pool_pre_ping=True)


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
    """Create local-only sample tenant, identity mappings, model catalog, and memberships."""
    if os.getenv("ENVIRONMENT", "").strip().lower() not in {"development", "test"}:
        raise RuntimeError("Development data seeding is restricted to development and test environments")
    from features.persistence import IdentitySourceMappingRecord

    demo_data_enabled = os.getenv("DEMO_DATA_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    if not demo_data_enabled:
        # Remove only explicitly marked identity-mapping fixtures; synchronized records are preserved.
        with SessionFactory.begin() as session:
            session.execute(
                delete(IdentitySourceMappingRecord).where(IdentitySourceMappingRecord.is_demo.is_(True))
            )
        return

    from features.persistence import (
        IdentitySourceMappingRecord,
        ModelBackendRecord,
        TenantMembershipRecord,
        TenantRecord,
    )
    from shared.authorization.jwt_handler import DEVELOPMENT_ISSUER
    from shared.authorization.roles import Role

    now = int(time.time())
    with SessionFactory.begin() as session:
        tenants = {
            "tenant-acme": ("Acme Corp", "acme-corp"),
            "tenant-contoso": ("Contoso Customer", "contoso-customer"),
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

        sample_identity_mappings = [
            {
                "id": "demo-map-entra-payments",
                "source_system": "entra_workforce",
                "source_instance": "https://login.microsoftonline.com/demo-workforce-tenant/v2.0",
                "record_type": "group",
                "external_id": "11111111-1111-4111-8111-111111111111",
                "display_name": "Payments AI Product Team",
                "tenant_id": "tenant-acme",
                "roles": [Role.DEVELOPER.value],
            },
            {
                "id": "demo-map-entra-platform-security",
                "source_system": "entra_workforce",
                "source_instance": "https://login.microsoftonline.com/demo-workforce-tenant/v2.0",
                "record_type": "group",
                "external_id": "22222222-2222-4222-8222-222222222222",
                "display_name": "AI Platform Security Reviewers",
                "tenant_id": "platform",
                "roles": [Role.AUDITOR.value],
            },
            {
                "id": "demo-map-entra-agent-payments",
                "source_system": "entra_agent_id",
                "source_instance": "demo-workforce-directory",
                "record_type": "agent_identity",
                "external_id": "33333333-3333-4333-8333-333333333333",
                "display_name": "Payments Support Agent",
                "tenant_id": "tenant-acme",
                "roles": [],
            },
            {
                "id": "demo-map-okta-ciam-contoso",
                "source_system": "okta_ciam",
                "source_instance": "https://demo-customer.okta.com/oauth2/default",
                "record_type": "customer_group",
                "external_id": "00g-demo-contoso-customers",
                "display_name": "Contoso Customer Users",
                "tenant_id": "tenant-contoso",
                "roles": [Role.VIEWER.value],
            },
        ]
        for mapping in sample_identity_mappings:
            if session.get(IdentitySourceMappingRecord, mapping["id"]) is None:
                session.add(IdentitySourceMappingRecord(
                    **mapping,
                    is_demo=True,
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
