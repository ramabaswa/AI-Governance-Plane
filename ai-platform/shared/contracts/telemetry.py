"""Contracts for Observability, Request Traces, and FinOps Metrics."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    span_id: str
    name: str
    start_time_ms: int
    duration_ms: int
    attributes: Dict[str, Any] = Field(default_factory=dict)


class RequestTrace(BaseModel):
    trace_id: str
    tenant_id: str
    application_id: str
    virtual_key_prefix: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    status_code: int
    dlp_redactions_count: int = 0
    timestamp: int
    spans: List[TraceSpan] = Field(default_factory=list)


class ObservedTrace(BaseModel):
    """Trace summary fields returned by Tempo without inferred token or cost values."""

    trace_id: str
    tenant_id: str
    root_service_name: Optional[str] = None
    root_trace_name: Optional[str] = None
    start_time_unix_nano: Optional[int] = None
    duration_ms: Optional[float] = None


class BudgetPolicy(BaseModel):
    tenant_id: str
    monthly_budget_usd: float
    alert_threshold_pct: int = 80
    current_spend_usd: float = 0.0
    hard_cap_enabled: bool = True
    hard_cap_action: str = "reject_429"
    updated_at: int
