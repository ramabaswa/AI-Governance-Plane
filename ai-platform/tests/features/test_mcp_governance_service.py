"""Focused unit tests for MCP registration safety and policy state."""

import pytest

from features.mcp_governance import service
from shared.contracts.mcp import MCPServerCreate, MCPToolPolicy
from shared.errors.exceptions import ValidationError


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp.example.test/rpc",
        "https://user:password@mcp.example.test/rpc",
        "https://mcp.example.test/rpc?token=secret",
        "https://mcp.example.test/rpc#fragment",
    ],
)
def test_registration_rejects_unsafe_transport_urls(feature_session, url):
    with pytest.raises(ValidationError):
        service.register_server(
            feature_session,
            tenant_id="tenant-acme",
            actor="admin",
            request=MCPServerCreate(name="test-server", transport_url=url),
        )


def test_tool_policy_requires_discovery_and_is_explicitly_non_enforcing(feature_session):
    server = service.register_server(
        feature_session,
        tenant_id="tenant-acme",
        actor="admin",
        request=MCPServerCreate(
            name="test-server",
            transport_url="https://mcp.example.test/rpc",
        ),
    )
    with pytest.raises(ValidationError, match="Discover tools"):
        service.update_tool_policy(
            feature_session,
            tenant_id="tenant-acme",
            server_id=server.id,
            actor="admin",
            policy=MCPToolPolicy(tool_name="lookup", cel_rule="true"),
        )
