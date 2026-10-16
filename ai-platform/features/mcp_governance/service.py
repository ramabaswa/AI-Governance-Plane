"""MCP registry with allowlisted, real tools/list discovery."""

import json
import os
import time
import uuid
from urllib.parse import urlsplit
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from features.audit_evidence.service import append_event
from features.persistence import MCPServerRecord
from shared.contracts.audit import AuditAction
from shared.contracts.mcp import MCPServer, MCPServerCreate, MCPTool, MCPToolPolicy
from shared.errors.exceptions import (
    GatewayReconciliationError,
    ResourceConflictError,
    ResourceNotFoundError,
    ValidationError,
)
from shared.validation.cel_validator import validate_cel_expression


def _contract(row: MCPServerRecord) -> MCPServer:
    return MCPServer(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        transport_url=row.transport_url,
        description=row.description,
        discovered_tools=[MCPTool.model_validate(tool) for tool in row.discovered_tools],
        policies=[MCPToolPolicy.model_validate(policy) for policy in row.policies],
        is_connected=False,
        discovery_state=row.discovery_state,
        policy_enforcement_state="not_published_to_gateway",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_servers(session: Session, tenant_id: str) -> list[MCPServer]:
    rows = session.scalars(
        select(MCPServerRecord)
        .where(MCPServerRecord.tenant_id == tenant_id)
        .order_by(MCPServerRecord.created_at.desc())
    ).all()
    return [_contract(row) for row in rows]


def get_server(session: Session, *, tenant_id: str, server_id: str) -> MCPServerRecord:
    row = session.scalar(
        select(MCPServerRecord).where(
            MCPServerRecord.id == server_id,
            MCPServerRecord.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ResourceNotFoundError("MCP server", server_id)
    return row


def register_server(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    request: MCPServerCreate,
) -> MCPServer:
    _validate_transport_url(request.transport_url, require_allowlist=False)
    existing = session.scalar(
        select(MCPServerRecord.id).where(
            MCPServerRecord.tenant_id == tenant_id,
            MCPServerRecord.name == request.name,
        )
    )
    if existing is not None:
        raise ResourceConflictError(f"MCP server '{request.name}' already exists in this tenant")
    for policy in request.initial_policies:
        validate_cel_expression(policy.cel_rule)
    now = int(time.time())
    row = MCPServerRecord(
        id=f"mcp-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        name=request.name,
        transport_url=request.transport_url,
        description=request.description,
        discovered_tools=[],
        policies=[policy.model_dump(mode="json") for policy in request.initial_policies],
        discovery_state="unverified",
        created_by=actor,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.MCP_REGISTERED,
        resource_type="mcp_server",
        resource_id=row.id,
        details={"name": row.name, "host": urlsplit(row.transport_url).hostname},
    )
    session.flush()
    return _contract(row)


def discover_tools(
    session: Session,
    *,
    tenant_id: str,
    server_id: str,
    actor: str,
) -> MCPServer:
    row = get_server(session, tenant_id=tenant_id, server_id=server_id)
    host = _validate_transport_url(row.transport_url, require_allowlist=True)
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            initialized = _rpc(
                client,
                row.transport_url,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "ai-governance-plane", "version": "0.1.0"},
                }},
            )
            if not isinstance(initialized.get("result"), dict):
                raise ValidationError("MCP initialize response did not contain a result")
            session_id = initialized.get("_session_id")
            headers = {"MCP-Protocol-Version": "2025-03-26"}
            if isinstance(session_id, str) and session_id:
                headers["MCP-Session-Id"] = session_id
            _rpc(
                client,
                row.transport_url,
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers,
            )
            listed = _rpc(
                client,
                row.transport_url,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                headers=headers,
            )
    except ValidationError:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise GatewayReconciliationError(
            "MCP discovery request failed; the previously stored tool snapshot is unchanged"
        ) from error

    result = listed.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise ValidationError("MCP tools/list response has no tools array")
    normalized = []
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ValidationError("MCP tools/list returned a malformed tool")
        input_schema = tool.get("inputSchema", {})
        if not isinstance(input_schema, dict):
            raise ValidationError("MCP tool inputSchema must be a JSON object")
        normalized.append({
            "name": tool["name"],
            "description": tool.get("description"),
            "input_schema": input_schema,
            "is_sensitive": False,
            "requires_hitl_approval": False,
        })
    row.discovered_tools = normalized
    row.discovery_state = "discovered"
    row.updated_at = int(time.time())
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.MCP_DISCOVERED,
        resource_type="mcp_server",
        resource_id=row.id,
        details={"tool_count": len(normalized), "host": host},
    )
    session.flush()
    return _contract(row)


def update_tool_policy(
    session: Session,
    *,
    tenant_id: str,
    server_id: str,
    actor: str,
    policy: MCPToolPolicy,
) -> MCPServer:
    row = get_server(session, tenant_id=tenant_id, server_id=server_id)
    if row.discovery_state != "discovered":
        raise ValidationError("Discover tools from the MCP server before assigning a tool policy")
    if not any(tool.get("name") == policy.tool_name for tool in row.discovered_tools):
        raise ResourceNotFoundError("MCP tool", policy.tool_name)
    validate_cel_expression(policy.cel_rule)
    policies = [item for item in row.policies if item.get("tool_name") != policy.tool_name]
    policies.append(policy.model_dump(mode="json"))
    row.policies = policies
    row.updated_at = int(time.time())
    append_event(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.MCP_POLICY_UPDATED,
        resource_type="mcp_policy",
        resource_id=f"{row.id}:{policy.tool_name}",
        details={"enabled": policy.is_enabled, "allowed_roles": policy.allowed_roles},
    )
    session.flush()
    return _contract(row)


def _validate_transport_url(value: str, *, require_allowlist: bool) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValidationError("MCP endpoint must be an HTTPS URL without credentials, query, or fragment")
    if require_allowlist:
        allowed_hosts = {
            item.strip().lower()
            for item in os.getenv("MCP_ALLOWED_HOSTS", "").split(",")
            if item.strip()
        }
        if not allowed_hosts or host.lower() not in allowed_hosts:
            raise ValidationError("MCP endpoint host is not in the configured MCP_ALLOWED_HOSTS allowlist")
    return host


def _rpc(
    client: httpx.Client,
    endpoint: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-03-26",
        **(headers or {}),
    }
    response = client.post(endpoint, json=payload, headers=request_headers)
    response.raise_for_status()
    if "id" not in payload:
        return {}
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        content = next(
            (
                line.removeprefix("data:").strip()
                for line in response.text.splitlines()
                if line.startswith("data:")
            ),
            "",
        )
        if not content:
            raise ValidationError("MCP server returned an empty event stream")
        result = json.loads(content)
    else:
        result = response.json()
    if not isinstance(result, dict):
        raise ValidationError("MCP server returned an invalid JSON-RPC response")
    if "error" in result:
        raise ValidationError("MCP server rejected a discovery request")
    if response.headers.get("MCP-Session-Id"):
        result["_session_id"] = response.headers["MCP-Session-Id"]
    return result
