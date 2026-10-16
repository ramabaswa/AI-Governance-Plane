"""Scope tenant memberships by OIDC issuer and subject."""

import os

from alembic import op
import sqlalchemy as sa

revision = "0003_issuer_scoped_memberships"
down_revision = "0002_governance_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    legacy_issuer = (
        os.getenv("OIDC_LEGACY_MEMBERSHIP_ISSUER")
        or os.getenv("OIDC_ISSUER")
        or ""
    ).strip()
    if not legacy_issuer:
        raise RuntimeError(
            "Set OIDC_LEGACY_MEMBERSHIP_ISSUER to the issuer of existing tenant memberships "
            "before upgrading to issuer-scoped memberships"
        )
    op.add_column(
        "tenant_memberships",
        sa.Column("issuer", sa.String(length=512), nullable=True),
    )
    op.get_bind().execute(
        sa.text("UPDATE tenant_memberships SET issuer = :issuer WHERE issuer IS NULL"),
        {"issuer": legacy_issuer},
    )
    op.alter_column("tenant_memberships", "issuer", nullable=False)
    op.drop_constraint(
        "uq_membership_subject_tenant",
        "tenant_memberships",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_membership_issuer_subject_tenant",
        "tenant_memberships",
        ["issuer", "subject", "tenant_id"],
    )
    op.create_index(
        "ix_tenant_memberships_issuer",
        "tenant_memberships",
        ["issuer"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_memberships_issuer", table_name="tenant_memberships")
    op.drop_constraint(
        "uq_membership_issuer_subject_tenant",
        "tenant_memberships",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_membership_subject_tenant",
        "tenant_memberships",
        ["subject", "tenant_id"],
    )
    op.drop_column("tenant_memberships", "issuer")
