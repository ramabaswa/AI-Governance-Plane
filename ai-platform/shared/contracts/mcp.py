"""Contracts for Model Context Protocol (MCP) tool server governance."""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class MCPTool(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    is_sensitive: bool = False
    requires_hitl_approval: bool = False


class MCPToolPolicy(BaseModel):
    tool_name: str
    cel_rule: str = Field(default="true", description="CEL authorization expression")
    allowed_roles: List[str] = Field(default_factory=list)
    is_enabled: bool = True


class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    transport_url: str = Field(..., description="HTTP or SSE endpoint URL for MCP server")
    description: Optional[str] = None
    initial_policies: List[MCPToolPolicy] = Field(default_factory=list)


class MCPServer(BaseModel):
    id: str
    tenant_id: str
    name: str
    transport_url: str
    description: Optional[str] = None
    discovered_tools: List[MCPTool] = Field(default_factory=list)
    policies: List[MCPToolPolicy] = Field(default_factory=list)
    is_connected: bool = False
    discovery_state: str = "unverified"
    policy_enforcement_state: str = "not_published_to_gateway"
    created_at: int
    updated_at: int
