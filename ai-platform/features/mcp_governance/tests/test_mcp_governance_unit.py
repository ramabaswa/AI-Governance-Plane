import pytest

from features.mcp_governance import service
from tests.feature_test_support import feature_database
from shared.contracts.mcp import MCPServerCreate
from shared.errors.exceptions import ValidationError


def test_registration_rejects_non_https_mcp_endpoint():
    with feature_database() as session:
        with pytest.raises(ValidationError, match="HTTPS"):
            service.register_server(
                session,
                tenant_id="tenant-acme",
                actor="admin",
                request=MCPServerCreate(
                    name="test-server",
                    transport_url="http://mcp.example.test/rpc",
                ),
            )
