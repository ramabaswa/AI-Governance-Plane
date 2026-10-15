"""Model Context Protocol (MCP) Governance router."""

import time
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from shared.contracts.mcp import MCPServer, MCPServerCreate, MCPTool, MCPToolPolicy
from shared.authorization.dependencies import (
    get_current_user,
    require_tenant_context,
    require_permission,
    AuthenticatedUser,
)
from shared.validation.cel_validator import validate_cel_expression
from shared.contracts.audit import AuditAction
from features.state_store import STATE_STORE

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Tool Governance"])


class DiscoverRequest(BaseModel):
    server_id: str


class ToolPolicyUpdateRequest(BaseModel):
    server_id: str
    tool_name: str
    cel_rule: str
    allowed_roles: List[str]
    is_enabled: bool = True


@router.get("/servers", response_model=List[MCPServer])
async def list_mcp_servers(
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List registered MCP servers."""
    return [s for s in STATE_STORE.mcp_servers.values() if s.tenant_id == tenant_id]


@router.post("/servers", status_code=201, response_model=MCPServer)
async def register_mcp_server(
    req: MCPServerCreate,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("mcp:create")),
):
    """Register an MCP tool server."""
    now = int(time.time())
    server = MCPServer(
        id=f"mcp-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        name=req.name,
        transport_url=req.transport_url,
        description=req.description,
        discovered_tools=[],
        policies=req.initial_policies,
        is_connected=True,
        created_at=now,
        updated_at=now,
    )
    STATE_STORE.mcp_servers[server.id] = server

    STATE_STORE.record_audit_event(
        tenant_id=tenant_id,
        actor=current_user.subject,
        action=AuditAction.MCP_REGISTERED,
        resource_type="mcp_server",
        resource_id=server.id,
        details={"name": server.name, "transport_url": server.transport_url},
    )
    return server


@router.post("/discover")
async def discover_tools(
    req: DiscoverRequest,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("mcp:create")),
):
    """Simulate tool introspection via JSON-RPC tools/list."""
    server = STATE_STORE.mcp_servers.get(req.server_id)
    if not server or server.tenant_id != tenant_id:
        from shared.errors.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("MCPServer", req.server_id)

    # Simulated introspected tools
    tools = [
        MCPTool(
            name="query_read",
            description="Execute read-only SQL query against replica",
            input_schema={"type": "object", "properties": {"sql": {"type": "string"}}},
            is_sensitive=False,
            requires_hitl_approval=False,
        ),
        MCPTool(
            name="drop_table",
            description="Destructive DDL drop operation",
            input_schema={"type": "object", "properties": {"table": {"type": "string"}}},
            is_sensitive=True,
            requires_hitl_approval=True,
        ),
    ]
    server.discovered_tools = tools
    return {
        "success": True,
        "tools_discovered": len(tools),
        "tools": tools,
    }


@router.post("/policies")
async def update_tool_policy(
    req: ToolPolicyUpdateRequest,
    tenant_id: str = Depends(require_tenant_context),
    current_user: AuthenticatedUser = Depends(require_permission("mcp:update")),
):
    """Update CEL-based fine-grained tool authorization policy."""
    server = STATE_STORE.mcp_servers.get(req.server_id)
    if not server or server.tenant_id != tenant_id:
        from shared.errors.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("MCPServer", req.server_id)

    validate_cel_expression(req.cel_rule)

    policy = MCPToolPolicy(
        tool_name=req.tool_name,
        cel_rule=req.cel_rule,
        allowed_roles=req.allowed_roles,
        is_enabled=req.is_enabled,
    )

    # Replace or append
    server.policies = [p for p in server.policies if p.tool_name != req.tool_name]
    server.policies.append(policy)

    STATE_STORE.record_audit_event(
        tenant_id=tenant_id,
        actor=current_user.subject,
        action=AuditAction.MCP_POLICY_UPDATED,
        resource_type="mcp_policy",
        resource_id=f"{server.id}:{req.tool_name}",
        details={"cel_rule": req.cel_rule},
    )

    return {
        "success": True,
        "policy": policy,
    }
