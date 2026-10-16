"""Contracts for Tamper-Evident Audit Evidence Ledger."""

import hashlib
import json
import time
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    AUTH_LOGIN = "AUTH_LOGIN"
    TENANT_CREATED = "TENANT_CREATED"
    MEMBERSHIP_CREATED = "MEMBERSHIP_CREATED"
    MEMBERSHIP_UPDATED = "MEMBERSHIP_UPDATED"
    APPLICATION_CREATED = "APPLICATION_CREATED"
    APPLICATION_LIFECYCLE_CHANGED = "APPLICATION_LIFECYCLE_CHANGED"
    VIRTUAL_KEY_MINTED = "VIRTUAL_KEY_MINTED"
    VIRTUAL_KEY_PROVISIONED = "VIRTUAL_KEY_PROVISIONED"
    VIRTUAL_KEY_PROVISION_FAILED = "VIRTUAL_KEY_PROVISION_FAILED"
    VIRTUAL_KEY_REVOKED = "VIRTUAL_KEY_REVOKED"
    VIRTUAL_KEY_REVOCATION_REQUESTED = "VIRTUAL_KEY_REVOCATION_REQUESTED"
    VIRTUAL_KEY_REVOCATION_SUBMITTED = "VIRTUAL_KEY_REVOCATION_SUBMITTED"
    MODEL_REGISTERED = "MODEL_REGISTERED"
    ROUTE_CREATED = "ROUTE_CREATED"
    ROUTE_UPDATED = "ROUTE_UPDATED"
    ROUTE_APPLY_REQUESTED = "ROUTE_APPLY_REQUESTED"
    ROUTE_OBSERVED_ACTIVE = "ROUTE_OBSERVED_ACTIVE"
    ROUTE_STATUS_CHANGED = "ROUTE_STATUS_CHANGED"
    POLICY_APPLIED = "POLICY_APPLIED"
    POLICY_APPROVAL_REQUESTED = "POLICY_APPROVAL_REQUESTED"
    POLICY_APPROVAL_DECIDED = "POLICY_APPROVAL_DECIDED"
    POLICY_APPROVAL_APPLIED = "POLICY_APPROVAL_APPLIED"
    ONBOARDING_REQUESTED = "ONBOARDING_REQUESTED"
    ONBOARDING_DECIDED = "ONBOARDING_DECIDED"
    ONBOARDING_COMPLETED = "ONBOARDING_COMPLETED"
    BUDGET_POLICY_UPDATED = "BUDGET_POLICY_UPDATED"
    POLICY_REVISION_CREATED = "POLICY_REVISION_CREATED"
    POLICY_REVISION_STATE_CHANGED = "POLICY_REVISION_STATE_CHANGED"
    POLICY_ROLLED_BACK = "POLICY_ROLLED_BACK"
    MCP_REGISTERED = "MCP_REGISTERED"
    MCP_DISCOVERED = "MCP_DISCOVERED"
    MCP_POLICY_UPDATED = "MCP_POLICY_UPDATED"
    AUDIT_READ = "AUDIT_READ"
    DRIFT_RECONCILED = "DRIFT_RECONCILED"


class AuditEvent(BaseModel):
    id: str
    tenant_id: str
    actor: str
    action: AuditAction
    resource_type: str
    resource_id: str
    payload_hash: str
    details: Dict[str, Any] = Field(default_factory=dict)
    prev_event_hash: str
    event_hash: str
    timestamp: int

    @staticmethod
    def calculate_event_hash(
        event_id: str,
        tenant_id: str,
        actor: str,
        action: str,
        resource_id: str,
        payload_hash: str,
        prev_hash: str,
        timestamp: int,
        resource_type: str = "",
    ) -> str:
        data = (
            f"{event_id}|{tenant_id}|{actor}|{action}|{resource_type}|"
            f"{resource_id}|{payload_hash}|{prev_hash}|{timestamp}"
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
