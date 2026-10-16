import pytest

from features.tenant_access import service
from tests.feature_test_support import feature_database
from shared.authorization.roles import Role
from shared.contracts.tenant import TenantMembershipCreate
from shared.errors.exceptions import ValidationError


def test_platform_admin_role_cannot_be_assigned_to_tenant_membership():
    with feature_database() as session:
        with pytest.raises(ValidationError, match="platform_admin"):
            service.create_membership(
                session,
                tenant_id="tenant-acme",
                actor="root",
                request=TenantMembershipCreate(
                    issuer="https://identity.example.test/",
                    subject="new-user",
                    roles=[Role.PLATFORM_ADMIN],
                ),
            )


def test_tenant_admin_membership_is_persisted_and_listed():
    with feature_database() as session:
        created = service.create_membership(
            session,
            tenant_id="tenant-acme",
            actor="root",
            request=TenantMembershipCreate(
                issuer="https://identity.example.test/",
                subject="new-user",
                roles=[Role.DEVELOPER],
            ),
        )
        memberships = service.list_memberships(session, "tenant-acme")
        assert created.subject == "new-user"
        assert created.issuer == "https://identity.example.test/"
        assert [membership.subject for membership in memberships] == ["new-user"]
