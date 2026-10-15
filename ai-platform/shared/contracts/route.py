"""Contracts for Gateway Traffic Routes and Native DLP Guardrails."""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class DLPAction(str, Enum):
    MASK = "Mask"
    BLOCK = "Block"


class PromptGuardRule(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    regex_patterns: List[str] = Field(..., min_items=1)
    action: DLPAction = DLPAction.MASK
    description: Optional[str] = None


class GatewayRouteCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    path_prefix: str = Field(..., min_length=1, max_length=256)
    backend_model_id: str
    failover_model_ids: List[str] = Field(default_factory=list)
    traffic_weights: Optional[Dict[str, int]] = Field(default=None)
    dlp_rules: List[PromptGuardRule] = Field(default_factory=list)
    rate_limit_rpm: Optional[int] = Field(default=None, gt=0)


class RouteValidationResult(BaseModel):
    is_valid: bool
    status: str = "validated" # Notice: STRICT RULE: Never returns "applied" or "observed_active"!
    kubernetes_crds: str
    warnings: List[str] = Field(default_factory=list)


class GatewayRoute(BaseModel):
    id: str
    tenant_id: str
    name: str
    path_prefix: str
    backend_model_id: str
    failover_model_ids: List[str]
    traffic_weights: Dict[str, int]
    dlp_rules: List[PromptGuardRule]
    rate_limit_rpm: Optional[int]
    revision_id: int
    lifecycle_state: str = "draft"
    created_at: int
    updated_at: int
