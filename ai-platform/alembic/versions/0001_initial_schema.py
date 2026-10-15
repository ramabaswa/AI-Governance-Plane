"""Create tenant-scoped governance, route, and audit tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("subject", "tenant_id", name="uq_membership_subject_tenant"),
    )
    op.create_index("ix_tenant_memberships_subject", "tenant_memberships", ["subject"])
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])

    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("allowed_models", sa.JSON(), nullable=False),
        sa.Column("monthly_token_quota", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("virtual_key_prefix", sa.String(length=24), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_application_tenant_name"),
    )
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"])

    op.create_table(
        "virtual_keys",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("application_id", sa.String(length=64), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("provisioning_state", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("key_hash", name="uq_virtual_keys_key_hash"),
    )
    op.create_index("ix_virtual_keys_tenant_id", "virtual_keys", ["tenant_id"])
    op.create_index("ix_virtual_keys_application_id", "virtual_keys", ["application_id"])

    op.create_table(
        "model_backends",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("secret_ref", sa.String(length=256), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("cost_per_1k_input_tokens", sa.Float(), nullable=False),
        sa.Column("cost_per_1k_output_tokens", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_model_tenant_name"),
    )
    op.create_index("ix_model_backends_tenant_id", "model_backends", ["tenant_id"])

    op.create_table(
        "gateway_routes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("path_prefix", sa.String(length=256), nullable=False),
        sa.Column("backend_model_id", sa.String(length=64), sa.ForeignKey("model_backends.id"), nullable=False),
        sa.Column("failover_model_ids", sa.JSON(), nullable=False),
        sa.Column("traffic_weights", sa.JSON(), nullable=False),
        sa.Column("dlp_rules", sa.JSON(), nullable=False),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=True),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_route_tenant_name"),
    )
    op.create_index("ix_gateway_routes_tenant_id", "gateway_routes", ["tenant_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("prev_event_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.Integer(), nullable=False),
        sa.UniqueConstraint("event_hash", name="uq_audit_events_event_hash"),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_table(
        "audit_chain_head",
        sa.Column("tenant_id", sa.String(length=128), primary_key=True),
        sa.Column("last_event_hash", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_chain_head")
    op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_gateway_routes_tenant_id", table_name="gateway_routes")
    op.drop_table("gateway_routes")
    op.drop_index("ix_model_backends_tenant_id", table_name="model_backends")
    op.drop_table("model_backends")
    op.drop_index("ix_virtual_keys_application_id", table_name="virtual_keys")
    op.drop_index("ix_virtual_keys_tenant_id", table_name="virtual_keys")
    op.drop_table("virtual_keys")
    op.drop_index("ix_applications_tenant_id", table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_subject", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
    op.drop_table("tenants")
