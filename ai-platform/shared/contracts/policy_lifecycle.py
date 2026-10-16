"""Contracts for route policy revision history."""

from typing import Any

from pydantic import BaseModel


class PolicyRevision(BaseModel):
    id: str
    tenant_id: str
    resource_type: str
    resource_id: str
    revision: int
    state: str
    snapshot: dict[str, Any]
    checksum: str
    created_by: str
    created_at: int
    updated_at: int
