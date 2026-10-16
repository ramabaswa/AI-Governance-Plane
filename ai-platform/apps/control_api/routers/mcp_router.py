"""Tenant-scoped MCP server registration, discovery, and tool policies."""

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from features.database import get_db_session
from features.mcp_governance import service
from shared.authorization.dependencies import (
    AuthenticatedUser,
    require_permission,
    require_tenant_context,
)
from shared.contracts.mcp import MCPServer, MCPServerCreate, MCPToolPolicy

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Tool Governance"])


class ToolPolicyRequest(BaseModel):
    policy: MCPToolPolicy


@router.get("/servers", response_model=list[MCPServer])
async def list_servers(
    tenant_id: str = Depends(require_tenant_context),
    _user: AuthenticatedUser = Depends(require_permission("mcp:read")),
    session: Session = Depends(get_db_session),
):
    return service.list_servers(session, tenant_id)


@router.post("/servers", status_code=201, response_model=MCPServer)
async def register_server(
    request: MCPServerCreate,
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("mcp:create")),
    session: Session = Depends(get_db_session),
):
    return service.register_server(
        session,
        tenant_id=tenant_id,
        actor=user.subject,
        request=request,
    )


@router.post("/servers/{server_id}/discover", response_model=MCPServer)
async def discover_tools(
    server_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("mcp:discover")),
    session: Session = Depends(get_db_session),
):
    """Call the registered server's real MCP initialize/tools/list methods."""
    return service.discover_tools(
        session,
        tenant_id=tenant_id,
        server_id=server_id,
        actor=user.subject,
    )


@router.put("/servers/{server_id}/policy", response_model=MCPServer)
async def update_tool_policy(
    request: ToolPolicyRequest,
    server_id: str = Path(...),
    tenant_id: str = Depends(require_tenant_context),
    user: AuthenticatedUser = Depends(require_permission("mcp:update")),
    session: Session = Depends(get_db_session),
):
    return service.update_tool_policy(
        session,
        tenant_id=tenant_id,
        server_id=server_id,
        actor=user.subject,
        policy=request.policy,
    )
