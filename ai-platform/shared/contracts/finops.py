"""Contracts for observed spend reporting and budget configuration."""

from pydantic import BaseModel, Field


class BudgetPolicyUpdate(BaseModel):
    monthly_budget_usd: float = Field(..., gt=0, le=1_000_000_000)
    alert_threshold_pct: int = Field(default=80, ge=1, le=100)
    hard_cap_enabled: bool = False


class BudgetPolicyView(BaseModel):
    tenant_id: str
    configured: bool
    monthly_budget_usd: float
    alert_threshold_pct: int
    updated_by: str
    updated_at: int
    current_spend_usd: float | None
    spend_source: str
    hard_cap_enforcement: str
