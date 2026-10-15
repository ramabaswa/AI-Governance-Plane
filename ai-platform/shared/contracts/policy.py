"""Contracts for Policy Lifecycle and Human-in-the-Loop (HITL) Approvals."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PolicyState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    APPLYING = "applying"
    OBSERVED_ACTIVE = "observed_active"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalRequestCreate(BaseModel):
    policy_type: str = Field(..., description="e.g. route_mutation, mcp_tool_access, budget_override")
    target_resource_id: str
    target_environment: str = "production"
    change_summary: str
    proposed_diff: str


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    comments: Optional[str] = None


class ApprovalRequest(BaseModel):
    id: str
    tenant_id: str
    policy_type: str
    target_resource_id: str
    target_environment: str
    change_summary: str
    proposed_diff: str
    requested_by: str
    status: str = "pending" # pending, approved, denied
    decided_by: Optional[str] = None
    decided_at: Optional[int] = None
    decision_comments: Optional[str] = None
    created_at: int
