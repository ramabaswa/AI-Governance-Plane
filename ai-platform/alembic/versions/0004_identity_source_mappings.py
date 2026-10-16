"""Add external identity source mapping registry for demo and synchronized records."""

from alembic import op
import sqlalchemy as sa

revision = "0004_identity_source_mappings"
down_revision = "0003_issuer_scoped_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_source_mappings",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_instance", sa.String(length=512), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "source_system", "source_instance", "record_type", "external_id",
            name="uq_identity_source_mapping_external_record",
        ),
    )
    op.create_index("ix_identity_source_mappings_source_system", "identity_source_mappings", ["source_system"])
    op.create_index("ix_identity_source_mappings_tenant_id", "identity_source_mappings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_identity_source_mappings_tenant_id", table_name="identity_source_mappings")
    op.drop_index("ix_identity_source_mappings_source_system", table_name="identity_source_mappings")
    op.drop_table("identity_source_mappings")
