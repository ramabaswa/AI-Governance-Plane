"""Add approvals, onboarding, budgets, MCP registry, and policy revisions."""

from alembic import op
import sqlalchemy as sa

revision = "0002_governance_workflows"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("policy_type", sa.String(length=64), nullable=False),
        sa.Column("target_resource_id", sa.String(length=128), nullable=False),
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("proposed_diff", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("decided_at", sa.Integer(), nullable=True),
        sa.Column("decision_comments", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])

    op.create_table(
        "onboarding_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("request_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.Integer(), nullable=True),
        sa.Column("review_comments", sa.Text(), nullable=True),
        sa.Column("application_id", sa.String(length=64), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("completed_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_onboarding_requests_tenant_id", "onboarding_requests", ["tenant_id"])

    op.create_table(
        "budget_policies",
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("monthly_budget_usd", sa.Float(), nullable=False),
        sa.Column("alert_threshold_pct", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )

    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("transport_url", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discovered_tools", sa.JSON(), nullable=False),
        sa.Column("policies", sa.JSON(), nullable=False),
        sa.Column("discovery_state", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_mcp_server_tenant_name"),
    )
    op.create_index("ix_mcp_servers_tenant_id", "mcp_servers", ["tenant_id"])

    op.create_table(
        "policy_revisions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "resource_id", "revision", name="uq_policy_revision_resource"),
    )
    op.create_index("ix_policy_revisions_tenant_id", "policy_revisions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_revisions_tenant_id", table_name="policy_revisions")
    op.drop_table("policy_revisions")
    op.drop_index("ix_mcp_servers_tenant_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
    op.drop_table("budget_policies")
    op.drop_index("ix_onboarding_requests_tenant_id", table_name="onboarding_requests")
    op.drop_table("onboarding_requests")
    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_table("approval_requests")
